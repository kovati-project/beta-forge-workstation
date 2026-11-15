"""
Apply rlimits and a seccomp filter to this process, then exec the snippet.

Usage: python3 -I sandbox.py <script>

Both survive execve and can only be tightened, never loosened, by the snippet.
libseccomp sets PR_SET_NO_NEW_PRIVS before loading the filter, so no setuid
binary can escape it either.
"""

import errno
import os
import resource
import socket
import sys

import seccomp

MiB = 1024 * 1024

cpu = int(os.environ.pop("SANDBOX_CPU_SECONDS", "10"))
LIMITS = {
    resource.RLIMIT_CPU: cpu,
    resource.RLIMIT_AS: 512 * MiB,
    resource.RLIMIT_FSIZE: 16 * MiB,
    resource.RLIMIT_NOFILE: 64,
    resource.RLIMIT_NPROC: 64,
    resource.RLIMIT_CORE: 0,
}
for res, value in LIMITS.items():
    resource.setrlimit(res, (value, value))

deny = seccomp.ERRNO(errno.EPERM)
f = seccomp.SyscallFilter(defaction=seccomp.ALLOW)
# No network: only local (AF_UNIX) sockets, which multiprocessing needs.
f.add_rule(deny, "socket", seccomp.Arg(0, seccomp.NE, socket.AF_UNIX))
for name in (
    "io_uring_setup", "io_uring_enter", "io_uring_register",  # sockets without socket()
    "ptrace", "process_vm_readv", "process_vm_writev", "pidfd_getfd",
    "unshare", "setns", "mount", "bpf", "perf_event_open",
    "keyctl", "add_key", "request_key", "userfaultfd",
):
    f.add_rule(deny, name)
f.load()

script = sys.argv[1]
os.execv(sys.executable, [sys.executable, "-I", "-B", script])
