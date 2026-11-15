"""
PID 1 of mcp-code-exec: the only process that can change uid.

The container starts this as uid 0 holding exactly two capabilities, SETUID and
SETGID (compose: ``cap_drop: [ALL]``, ``cap_add: [SETUID, SETGID]``,
``no-new-privileges``). It never touches the network. It:

1. starts the MCP server as uid 10001 with no capabilities, connected to this
   process by a private AF_UNIX SOCK_SEQPACKET socketpair;
2. on ``run``: forks a child that becomes uid 10002 (the sandbox uid, with no
   capabilities), writes the snippet to /scratch/main.py and execs sandbox.py,
   with stdout / stderr on pipe ends the server passed over the socket;
3. on ``sweep``: forks a helper that becomes uid 10002 and calls
   kill(-1, SIGKILL), which kills every process of that uid, including
   setsid()'d or double-forked ones, then empties /scratch, /dev/shm and
   /dev/mqueue of the sandbox's files. It repeats until /proc shows no
   sandbox-uid process;
4. reaps every child (it is PID 1) and reports run exit statuses.

The server cannot signal sandbox processes and a sandbox process cannot signal
the server or this process, because each runs under a different uid and none
holds CAP_KILL. no-new-privileges and the absence of setuid binaries mean
neither can regain capabilities.
"""

import errno
import json
import os
import signal
import socket
import sys
import time

SERVER_UID = 10001
SANDBOX_UID = 10002
SCRATCH = "/scratch"
SHARED_DIRS = ("/scratch", "/dev/shm", "/dev/mqueue")
PYTHON = "/usr/bin/python3"
HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.join(HERE, "sandbox.py")
SERVER = ["/opt/mcp/bin/python", os.path.join(HERE, "server.py")]
MAX_MSG = 256 * 1024

runs = {}        # pid -> run id
sweeps = {}      # pid -> sweep id
server_pid = None
sock = None


def send(msg: dict) -> None:
    sock.send(json.dumps(msg).encode())


def become(uid: int) -> None:
    """Irreversibly switch to ``uid`` (drops all capabilities)."""
    os.setgroups([])
    os.setgid(uid)
    os.setuid(uid)
    if os.getuid() != uid or os.geteuid() != uid:
        os._exit(70)


def sandbox_pids() -> list:
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/status") as f:
                for line in f:
                    if line.startswith("Uid:"):
                        if int(line.split()[1]) == SANDBOX_UID:
                            pids.append(int(entry))
                        break
        except OSError:
            pass
    return pids


def on_sigchld(*_):
    global server_pid
    while True:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return
        if pid == server_pid:
            os._exit(os.waitstatus_to_exitcode(status) or 1)
        run_id = runs.pop(pid, None)
        if run_id is not None:
            send({"op": "exit", "id": run_id, "status": os.waitstatus_to_exitcode(status)})
        sweeps.pop(pid, None)


def on_term(*_):
    if server_pid:
        try:
            os.kill(server_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    os._exit(0)


def start_run(msg: dict, fds: list) -> None:
    code = msg["code"]
    pid = os.fork()
    if pid == 0:
        try:
            os.setsid()
            become(SANDBOX_UID)
            os.dup2(fds[0], 1)
            os.dup2(fds[1], 2)
            null = os.open("/dev/null", os.O_RDONLY)
            os.dup2(null, 0)
            os.closerange(3, 65536)
            os.chdir(SCRATCH)
            fd = os.open("main.py", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.write(fd, code.encode("utf-8", "surrogatepass"))
            os.close(fd)
            env = {
                "PATH": "/usr/bin:/bin", "HOME": SCRATCH, "TMPDIR": SCRATCH,
                "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
                "SANDBOX_CPU_SECONDS": str(int(msg.get("cpu", 10))),
            }
            os.execve(PYTHON, [PYTHON, "-I", SANDBOX, os.path.join(SCRATCH, "main.py")], env)
        finally:
            os._exit(71)
    for fd in fds:
        os.close(fd)
    runs[pid] = msg["id"]
    send({"op": "started", "id": msg["id"], "pid": pid})


def wipe(path: str) -> None:
    """Delete everything under ``path`` that the current uid can delete."""
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            try:
                os.unlink(os.path.join(root, name))
            except OSError:
                pass
        for name in dirs:
            p = os.path.join(root, name)
            try:
                if os.path.islink(p):
                    os.unlink(p)
                else:
                    os.rmdir(p)
            except OSError:
                pass


def sweep(msg: dict) -> None:
    ok = False
    for _ in range(5):
        pid = os.fork()
        if pid == 0:
            try:
                os.closerange(3, 65536)
                become(SANDBOX_UID)
                for _ in range(3):
                    try:
                        os.kill(-1, signal.SIGKILL)
                    except OSError as e:
                        if e.errno != errno.ESRCH:
                            raise
                for d in SHARED_DIRS:
                    wipe(d)
                os._exit(0)
            finally:
                os._exit(72)
        sweeps[pid] = msg["id"]
        deadline = time.monotonic() + 5
        while pid in sweeps and time.monotonic() < deadline:
            time.sleep(0.01)   # SIGCHLD (on_sigchld) reaps the helper
        time.sleep(0.05)
        # Zombies of killed runs are reaped by on_sigchld; anything left with
        # the sandbox uid is still alive.
        if not sandbox_pids():
            ok = True
            break
    send({"op": "swept", "id": msg["id"], "ok": ok})


def main() -> None:
    global server_pid, sock
    if os.getuid() != 0:
        sys.exit("launcher must start as uid 0 (with only CAP_SETUID/CAP_SETGID)")
    ours, theirs = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    sock = ours
    signal.signal(signal.SIGCHLD, on_sigchld)
    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)

    server_pid = os.fork()
    if server_pid == 0:
        try:
            ours.close()
            become(SERVER_UID)
            os.chdir("/tmp")
            env = dict(os.environ)
            env["LAUNCHER_FD"] = str(theirs.fileno())
            os.set_inheritable(theirs.fileno(), True)
            os.execve(SERVER[0], SERVER, env)
        finally:
            os._exit(73)
    theirs.close()

    while True:
        try:
            data, fds, _flags, _addr = socket.recv_fds(sock, MAX_MSG, 4)
        except InterruptedError:
            continue
        if not data:
            on_term()
        msg = json.loads(data)
        if msg["op"] == "run":
            start_run(msg, fds)
        else:
            for fd in fds:
                os.close(fd)
            if msg["op"] == "sweep":
                sweep(msg)


if __name__ == "__main__":
    main()
