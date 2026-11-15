"""
mcp-code-exec: a minimal MCP server with one tool, ``run_python``.

There is no official MCP code-execution server, and the third-party ones either
run code with network access or are unmaintained, so this is deliberately small
enough to audit in one sitting.

Process layout (see launcher.py):

    launcher.py   uid 0, only CAP_SETUID + CAP_SETGID, PID 1, no network
     ├─ server.py uid 10001 (this file), no capabilities, serves MCP on :3102
     └─ runs      uid 10002, no capabilities, one at a time

Isolation, outermost first:

* Container (docker/compose.agentic.yml): read-only root filesystem,
  ``cap_drop: [ALL]`` + ``cap_add: [SETUID, SETGID]`` (held by the launcher
  only), ``no-new-privileges``, memory / CPU / pids limits. The port is
  published on the docker0 gateway address only (MCP_BIND).
* Snippets run as their own uid, so they cannot signal or inspect this server,
  the launcher, or files under /tmp (0700, owned by 10001). Their only
  writable space is /scratch (plus /dev/shm and /dev/mqueue), which is wiped
  after every run.
* Each run is a fresh ``python3 -I`` process started through ``sandbox.py``:
  rlimits plus a seccomp filter that refuses every non-AF_UNIX socket, so the
  snippet has no network. The filter also blocks io_uring, ptrace and
  cross-process memory access.
* After every run, whatever happened, the launcher kills every sandbox-uid
  process (kill(-1, SIGKILL) as that uid, which also catches setsid()'d and
  double-forked children) and wipes the scratch areas. Output reading has its
  own deadline, so a leftover process holding stdout cannot wedge a call.
* Runs are serialised: one sandbox uid and one scratch area, so one run can
  never see or touch another.
"""

import asyncio
import ctypes
import itertools
import json
import os
import socket
import sys

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

HOST = os.getenv("MCP_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_PORT", "3102"))
MAX_TIMEOUT = int(os.getenv("CODE_EXEC_MAX_TIMEOUT", "30"))
MAX_OUTPUT = int(os.getenv("CODE_EXEC_MAX_OUTPUT_BYTES", str(64 * 1024)))
MAX_CODE = 64 * 1024           # the run request is one SOCK_SEQPACKET message
MAX_MSG = 200_000              # under the default socket send buffer (~208 KiB)
DRAIN_GRACE = 5                # seconds to finish reading output after the sweep
LAUNCHER_REPLY_TIMEOUT = 20    # seconds for "started" / "swept"

# Host-header allowlist (DNS-rebinding protection), same policy as the
# mcp-proxy servers: loopback plus the comma-separated MCP_ALLOWED_HOSTS
# (host:port, or host:* for any port).
ALLOWED_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"] + [
    h.strip() for h in os.getenv("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()
]

PR_SET_DUMPABLE = 4

mcp = FastMCP(
    "code-exec",
    host=HOST,
    port=PORT,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=ALLOWED_HOSTS,
        allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
    ),
)


async def _drain(fd: int, limit: int) -> tuple:
    """Read a pipe to EOF, keeping at most ``limit`` bytes. Takes ownership of ``fd``."""
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    transport, _ = await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), os.fdopen(fd, "rb", 0))
    kept = bytearray()
    truncated = False
    try:
        while chunk := await reader.read(65536):
            room = limit - len(kept)
            if room > 0:
                kept += chunk[:room]
            if len(chunk) > room:
                truncated = True
    finally:
        transport.close()
    return bytes(kept), truncated


class Launcher:
    """Client for the launcher's socket. Replies are matched by (op, id)."""

    def __init__(self, fd: int):
        self.sock = socket.socket(fileno=fd)
        self.sock.setblocking(False)
        self.ids = itertools.count(1)
        self.waiters: dict = {}
        self.lock = None                 # created on the server's event loop
        self.reader = None

    def _future(self, op: str, rid: int) -> asyncio.Future:
        fut = asyncio.get_running_loop().create_future()
        self.waiters[(op, rid)] = fut
        return fut

    async def _read_loop(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            data = await loop.sock_recv(self.sock, 65536)
            if not data:
                os._exit(1)              # launcher gone: let the container restart
            msg = json.loads(data)
            fut = self.waiters.pop((msg["op"], msg["id"]), None)
            if fut and not fut.done():
                fut.set_result(msg)

    async def run(self, code: str, timeout: int) -> dict:
        loop = asyncio.get_running_loop()
        if self.lock is None:
            self.lock = asyncio.Lock()
        if self.reader is None or self.reader.done():
            self.reader = loop.create_task(self._read_loop())

        size = len(json.dumps({"op": "run", "id": 2**40, "code": code, "cpu": timeout},
                              ensure_ascii=False).encode())
        if size > MAX_MSG:
            return {"exit_code": None, "timed_out": False, "stdout": "",
                    "stderr": "code is too large", "truncated": False}

        async with self.lock:            # one run at a time
            rid = next(self.ids)
            payload = json.dumps({"op": "run", "id": rid, "code": code, "cpu": timeout},
                                 ensure_ascii=False).encode()
            out_r, out_w = os.pipe()
            err_r, err_w = os.pipe()
            started = self._future("started", rid)
            exited = self._future("exit", rid)
            swept = self._future("swept", rid)
            try:
                socket.send_fds(self.sock, [payload], [out_w, err_w])
            finally:
                # The launcher has its own copies now; ours must go, or EOF never comes.
                os.close(out_w)
                os.close(err_w)

            readers = asyncio.gather(_drain(out_r, MAX_OUTPUT), _drain(err_r, MAX_OUTPUT))
            timed_out = False
            status = None
            try:
                await asyncio.wait_for(started, LAUNCHER_REPLY_TIMEOUT)
                status = (await asyncio.wait_for(exited, timeout))["status"]
            except asyncio.TimeoutError:
                timed_out = True
            finally:
                # Always, also after a clean exit: kill every sandbox-uid process
                # (the snippet's process group and anything that escaped it) and
                # wipe the scratch areas.
                await loop.sock_sendall(self.sock, json.dumps({"op": "sweep", "id": rid}).encode())
                sweep = await asyncio.wait_for(swept, LAUNCHER_REPLY_TIMEOUT)
                self.waiters.pop(("exit", rid), None)
                self.waiters.pop(("started", rid), None)

            try:
                (out, out_trunc), (err, err_trunc) = await asyncio.wait_for(readers, DRAIN_GRACE)
            except asyncio.TimeoutError:
                # Every writer is dead after the sweep, so this should not
                # happen; if it does, give up on the output rather than wedge.
                out, err, out_trunc, err_trunc = b"", b"<output unavailable>", True, True

            if not sweep["ok"]:
                # A sandbox process survived SIGKILL; do not run anything else
                # in a dirty sandbox. Exiting makes the container restart.
                print("sweep failed; exiting", file=sys.stderr, flush=True)
                loop.call_later(0.5, os._exit, 1)
            return {
                "exit_code": status,
                "timed_out": timed_out,
                "stdout": out.decode("utf-8", "replace"),
                "stderr": err.decode("utf-8", "replace"),
                "truncated": out_trunc or err_trunc,
            }


launcher: Launcher = None


@mcp.tool()
async def run_python(code: str, timeout_seconds: int = 10) -> dict:
    """Run a Python 3 snippet in a sandbox and return its exit code, stdout and stderr.

    The sandbox has the standard library only, no network access, no persistent
    files (each run starts in an empty directory that is wiped afterwards), and
    limits on CPU time, memory and output size. Runs are queued one at a time.
    Print what you want to see; the value of the last expression is not returned.

    Args:
        code: Python source to execute (at most 64 KiB).
        timeout_seconds: wall-clock limit, 1-30 seconds (default 10).
    """
    if len(code.encode("utf-8", "surrogatepass")) > MAX_CODE:
        return {"exit_code": None, "timed_out": False, "stdout": "",
                "stderr": f"code is larger than {MAX_CODE} bytes", "truncated": False}
    timeout = max(1, min(int(timeout_seconds), MAX_TIMEOUT))
    return await launcher.run(code, timeout)


def main() -> None:
    global launcher
    if os.getuid() == 0:
        sys.exit("server.py must be started by launcher.py, not as root")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
        sys.exit("prctl(PR_SET_DUMPABLE) failed")
    launcher = Launcher(int(os.environ.pop("LAUNCHER_FD")))
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
