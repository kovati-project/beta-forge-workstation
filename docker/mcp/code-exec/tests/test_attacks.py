"""
Attack tests for mcp-code-exec (issue #99), run against the built image.

CI (.github/workflows/mcp-code-exec.yml) starts the container with the
compose security settings and runs this file. Locally:

    MCP_BIND=127.0.0.1 docker compose -f docker/compose.agentic.yml \
        --profile code-exec up -d --build mcp-code-exec
    MCP_CODE_EXEC_URL=http://localhost:3102/mcp pytest -v docker/mcp/code-exec/tests

Every call has a client-side deadline, so a wedged server fails the test
instead of hanging the job.
"""

import asyncio
import json
import os
import subprocess
import textwrap
import time

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = os.getenv("MCP_CODE_EXEC_URL", "http://localhost:3102/mcp")
CONTAINER = os.getenv("MCP_CODE_EXEC_CONTAINER", "mcp-code-exec")
CALL_DEADLINE = 60


async def _call(code: str, timeout: int = 10) -> dict:
    async with streamablehttp_client(URL) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("run_python", {"code": textwrap.dedent(code), "timeout_seconds": timeout})
            assert not res.isError, res
            return json.loads(res.content[0].text)


async def _call_deadline(code: str, timeout: int = 10) -> dict:
    return await asyncio.wait_for(_call(code, timeout), CALL_DEADLINE)


def run(code: str, timeout: int = 10) -> dict:
    return asyncio.run(_call_deadline(code, timeout))


def run_json(code: str, timeout: int = 10):
    out = run(code, timeout)
    assert out["exit_code"] == 0, out
    return json.loads(out["stdout"].strip().splitlines()[-1])


def with_procs(code: str) -> str:
    """Prefix ``code`` with a procs() helper that lists every process and its uid."""
    return textwrap.dedent(PROCS) + textwrap.dedent(code)


PROCS = """
    import os, json
    def procs():
        res = []
        for p in os.listdir('/proc'):
            if not p.isdigit():
                continue
            try:
                st = dict(l.split(':', 1) for l in open(f'/proc/{p}/status') if ':' in l)
            except OSError:
                continue
            res.append({'pid': int(p), 'name': st['Name'].strip(), 'uid': int(st['Uid'].split()[0])})
        return res
"""


# ── baseline guarantees ──────────────────────────────────────────────────────

def test_print_one_plus_one():
    out = run("print(1+1)")
    assert out["exit_code"] == 0 and out["stdout"] == "2\n", out


def test_no_network():
    res = run_json("""
        import socket, json, urllib.request
        r = {}
        for name, fam in (('inet', socket.AF_INET), ('inet6', socket.AF_INET6), ('netlink', socket.AF_NETLINK)):
            try:
                socket.socket(fam, socket.SOCK_RAW if fam == socket.AF_NETLINK else socket.SOCK_STREAM)
                r[name] = 'OPEN'
            except OSError as e:
                r[name] = e.errno
        try:
            urllib.request.urlopen('http://1.1.1.1', timeout=3)
            r['http'] = 'OPEN'
        except Exception as e:
            r['http'] = 'blocked'
        try:
            socket.getaddrinfo('example.com', 80)
            r['dns'] = 'OPEN'
        except OSError:
            r['dns'] = 'blocked'
        a, b = socket.socketpair()
        r['unix'] = 'ok'
        print(json.dumps(r))
    """)
    assert res == {"inet": 1, "inet6": 1, "netlink": 1, "http": "blocked", "dns": "blocked", "unix": "ok"}


def test_snippet_identity_has_no_capabilities():
    res = run_json("""
        import os, json
        st = dict(l.split(':', 1) for l in open('/proc/self/status') if ':' in l)
        print(json.dumps({'uid': os.getuid(), 'gid': os.getgid(), 'groups': os.getgroups(),
                          'capeff': st['CapEff'].strip(), 'capprm': st['CapPrm'].strip(),
                          'nnp': st['NoNewPrivs'].strip(), 'cwd': os.getcwd()}))
    """)
    assert res["uid"] == 10002 and res["gid"] == 10002 and res["groups"] == []
    assert int(res["capeff"], 16) == 0 and int(res["capprm"], 16) == 0
    assert res["nnp"] == "1"
    assert res["cwd"] == "/scratch"


def test_cpu_loop_is_stopped():
    t = time.monotonic()
    out = run("while True: pass", timeout=2)
    assert out["exit_code"] != 0
    assert time.monotonic() - t < 20


# ── #99 item 1: orphaned children must not wedge the server ─────────────────

WEDGE = """
import os, time, sys
if os.fork() == 0:
    os.setsid()
    if os.fork() == 0:          # double fork: not even in the snippet's session
        time.sleep(300)         # holds stdout / stderr open
    os._exit(0)
print('parent done', flush=True)
"""


def test_setsid_child_holding_stdout_does_not_wedge():
    async def scenario():
        t = time.monotonic()
        a, b = await asyncio.gather(_call_deadline(WEDGE, 3), _call_deadline(WEDGE, 3))
        third = await _call_deadline("print(1+1)")
        return a, b, third, time.monotonic() - t

    a, b, third, elapsed = asyncio.run(scenario())
    assert "parent done" in a["stdout"] and "parent done" in b["stdout"]
    assert third["stdout"] == "2\n"
    assert elapsed < 45, elapsed


def test_wedged_parent_times_out_and_nothing_survives():
    out = run(WEDGE + "\ntime.sleep(300)\n", timeout=2)
    assert out["timed_out"] is True
    others = run_json(with_procs("""
        me = os.getpid()
        print(json.dumps([p for p in procs() if p['uid'] == 10002 and p['pid'] != me]))
    """))
    assert others == [], others


# ── #99 items 2 and 5: the snippet cannot touch the server or the launcher ──

def test_cannot_stop_or_kill_server_or_launcher():
    res = run_json(with_procs("""
        import signal
        me = os.getpid()
        out = []
        for p in procs():
            if p['uid'] == 10002:
                continue
            for sig in (signal.SIGSTOP, signal.SIGKILL):
                try:
                    os.kill(p['pid'], sig)
                    out.append([p['pid'], p['uid'], sig, 'SENT'])
                except OSError as e:
                    out.append([p['pid'], p['uid'], sig, e.errno])
        print(json.dumps(out))
    """))
    uids = {uid for _, uid, _, _ in res}
    assert {0, 10001} <= uids, res                      # launcher and server were targeted
    assert all(r[3] == 1 for r in res), res             # every attempt: EPERM
    assert run("print(1+1)")["stdout"] == "2\n"         # and the server still answers


def test_cannot_read_server_or_launcher_environment():
    res = run_json(with_procs("""
        out = {}
        for p in procs():
            if p['uid'] != 10002:
                for f in ('environ', 'mem', 'fd'):
                    try:
                        os.listdir(f'/proc/{p["pid"]}/fd') if f == 'fd' else open(f'/proc/{p["pid"]}/{f}', 'rb').read(1)
                        out[f'{p["uid"]}/{f}'] = 'READABLE'
                    except OSError as e:
                        out[f'{p["uid"]}/{f}'] = e.errno
        print(json.dumps(out))
    """))
    assert res and all(v == 13 for v in res.values()), res


# ── #99 item 2: one run cannot tamper with another ──────────────────────────

def test_cannot_tamper_with_next_run():
    first = run("""
        import os, time
        open('/dev/shm/planted', 'w').write('x')
        if os.fork() == 0:
            os.setsid()
            if os.fork() == 0:
                for _ in range(3000):
                    for path in ('/scratch/main.py', '/scratch/planted'):
                        try:
                            open(path, 'w').write("print('TAMPERED')")
                        except OSError:
                            pass
                    time.sleep(0.01)
            os._exit(0)
        print('planted')
    """)
    assert "planted" in first["stdout"]
    second = run_json("""
        import os, json
        print(json.dumps({'scratch': sorted(os.listdir('/scratch')),
                          'shm': [f for f in os.listdir('/dev/shm') if f == 'planted'],
                          'mine': 'SECOND-RUN' in open('/scratch/main.py').read()}))  # SECOND-RUN
    """)
    assert second == {"scratch": ["main.py"], "shm": [], "mine": True}, second


def test_runs_do_not_overlap():
    code = "import time; a = time.time(); time.sleep(1.5); print(a, time.time())"

    async def both():
        return await asyncio.gather(_call_deadline(code), _call_deadline(code))

    a, b = asyncio.run(both())
    (s1, e1), (s2, e2) = (map(float, x["stdout"].split()) for x in (a, b))
    assert e1 <= s2 or e2 <= s1, (a, b)


# ── #99 item 3: /tmp is off limits and scratch is wiped ─────────────────────

def test_tmp_not_writable_by_sandbox():
    res = run_json("""
        import json, os
        r = {}
        for path in ('/tmp/x', '/x', '/opt/code-exec/x', '/var/tmp/x', '/home/x'):
            try:
                open(path, 'w').write('x')
                r[path] = 'WRITABLE'
            except OSError as e:
                r[path] = e.errno
        try:
            os.listdir('/tmp')
            r['list /tmp'] = 'LISTABLE'
        except OSError as e:
            r['list /tmp'] = e.errno
        print(json.dumps(r))
    """)
    assert all(v in (13, 30, 2) for v in res.values()), res
    assert res["/tmp/x"] == 13 and res["list /tmp"] == 13


def test_filling_scratch_and_shm_does_not_break_next_run():
    first = run("""
        import os
        for d in ('/scratch', '/dev/shm'):
            i = 0
            try:
                while True:
                    with open(f'{d}/fill{i}', 'wb') as f:
                        f.write(b'x' * (15 * 1024 * 1024))
                    i += 1
            except OSError as e:
                print(d, 'full after', i, e.errno)
    """, timeout=20)
    assert first["stdout"].count("full after") == 2, first
    second = run_json("""
        import os, json
        with open('/scratch/new', 'wb') as f:
            f.write(b'y' * (8 * 1024 * 1024))
        print(json.dumps({'scratch': sorted(os.listdir('/scratch')),
                          'shm_fill': [f for f in os.listdir('/dev/shm') if f.startswith('fill')]}))
    """)
    assert second == {"scratch": ["main.py", "new"], "shm_fill": []}, second


# ── process layout inside the container ─────────────────────────────────────

def test_process_layout():
    script = (
        "for p in /proc/[0-9]*; do "
        "  awk '/^(Name|Uid|CapEff|NoNewPrivs):/ {printf \"%s \", $2} END {print \"\"}' $p/status 2>/dev/null; "
        "done"
    )
    out = subprocess.run(["docker", "exec", CONTAINER, "sh", "-c", script],
                         capture_output=True, text=True, check=True).stdout
    rows = [line.split() for line in out.splitlines() if line.strip()]
    by_name = {}
    for name, uid, capeff, nnp in rows:
        if name == "python3" or name.startswith("python"):
            by_name.setdefault(uid, []).append((capeff, nnp))
    # launcher: uid 0 with exactly CAP_SETGID (bit 6) + CAP_SETUID (bit 7)
    assert ("00000000000000c0", "1") in by_name.get("0", []), rows
    # server: uid 10001 with no capabilities
    assert by_name.get("10001") == [("0000000000000000", "1")], rows
