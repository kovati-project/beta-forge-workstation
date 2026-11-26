"""
mcp-code-exec: a minimal MCP server with one tool, ``run_python``.

There is no official MCP code-execution server, and the third-party ones either
run code with network access or are unmaintained, so this is deliberately small
enough to audit in one sitting.

Isolation, outermost first:

* Container (docker/compose.agentic.yml): non-root, read-only root filesystem,
  ``cap_drop: [ALL]``, ``no-new-privileges``, memory / CPU / pids limits, and a
  size-capped tmpfs on /tmp as the only writable path.
* Each run is a fresh ``python3 -I`` process started through ``sandbox.py``,
  which applies rlimits (CPU time, address space, file size, open files,
  processes) and a seccomp filter that refuses every non-AF_UNIX socket, so the
  snippet has no network even though this server does. The filter also blocks
  io_uring, ptrace and cross-process memory access. It persists across exec and
  cannot be removed.
* The snippet gets an empty working directory under /tmp, a scrubbed
  environment, no inherited file descriptors, a wall-clock timeout, and bounded
  stdout / stderr. The whole process group is killed when it times out.
* This server marks itself non-dumpable, so the snippet (same uid) cannot read
  or write its memory through /proc.
"""

import asyncio
import ctypes
import os
import shutil
import signal
import sys
import tempfile

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

HOST = os.getenv("MCP_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_PORT", "3102"))
MAX_TIMEOUT = int(os.getenv("CODE_EXEC_MAX_TIMEOUT", "30"))
MAX_OUTPUT = int(os.getenv("CODE_EXEC_MAX_OUTPUT_BYTES", str(64 * 1024)))
MAX_CONCURRENT = int(os.getenv("CODE_EXEC_MAX_CONCURRENT", "2"))
SANDBOX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sandbox.py")
PYTHON = "/usr/bin/python3"

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
_slots = asyncio.Semaphore(MAX_CONCURRENT)


async def _drain(stream: asyncio.StreamReader, limit: int) -> tuple[bytes, bool]:
    """Read a stream to EOF, keeping at most ``limit`` bytes."""
    kept = bytearray()
    truncated = False
    while chunk := await stream.read(65536):
        room = limit - len(kept)
        if room > 0:
            kept += chunk[:room]
        if len(chunk) > room:
            truncated = True
    return bytes(kept), truncated


@mcp.tool()
async def run_python(code: str, timeout_seconds: int = 10) -> dict:
    """Run a Python 3 snippet in a sandbox and return its exit code, stdout and stderr.

    The sandbox has the standard library only, no network access, no persistent
    files (each run starts in an empty temporary directory that is deleted
    afterwards), and limits on CPU time, memory and output size. Print what you
    want to see; the value of the last expression is not returned.

    Args:
        code: Python source to execute.
        timeout_seconds: wall-clock limit, 1-30 seconds (default 10).
    """
    timeout = max(1, min(int(timeout_seconds), MAX_TIMEOUT))
    async with _slots:
        workdir = tempfile.mkdtemp(prefix="run-", dir="/tmp")
        try:
            script = os.path.join(workdir, "main.py")
            with open(script, "w", encoding="utf-8") as f:
                f.write(code)
            env = {
                "PATH": "/usr/bin:/bin",
                "HOME": workdir,
                "TMPDIR": workdir,
                "LANG": "C.UTF-8",
                "PYTHONDONTWRITEBYTECODE": "1",
                "SANDBOX_CPU_SECONDS": str(timeout),
            }
            proc = await asyncio.create_subprocess_exec(
                PYTHON, "-I", SANDBOX, script,
                cwd=workdir,
                env=env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                close_fds=True,
                start_new_session=True,
            )
            readers = asyncio.gather(_drain(proc.stdout, MAX_OUTPUT), _drain(proc.stderr, MAX_OUTPUT))
            timed_out = False
            try:
                await asyncio.wait_for(proc.wait(), timeout)
            except asyncio.TimeoutError:
                timed_out = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await proc.wait()
            (out, out_trunc), (err, err_trunc) = await readers
            return {
                "exit_code": proc.returncode,
                "timed_out": timed_out,
                "stdout": out.decode("utf-8", "replace"),
                "stderr": err.decode("utf-8", "replace"),
                "truncated": out_trunc or err_trunc,
            }
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


def main() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
        sys.exit("prctl(PR_SET_DUMPABLE) failed")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
