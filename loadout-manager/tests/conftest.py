"""
Shared fixtures for the Loadout Manager tests (gating/switching and api/*).

Nothing here talks to a GPU, a Docker daemon, or the live workstation:

* ``pynvml`` and ``docker`` are replaced with stubs in ``sys.modules`` BEFORE
  ``main`` is imported, so importing the app has no host side effects.
* ``subprocess.run`` (what ``main`` uses for ``docker compose``) is replaced by
  a recorder, ``FakeDocker``, that never executes anything.
* ``asyncio.sleep`` as seen by ``main`` is replaced so the 3 s GPU-release
  pause costs nothing (and so tests can park a switch mid-transition).
* State/schedule files are redirected into a temp dir; ``/data`` is never touched.

What this can NOT prove: that real ``docker compose`` honours the command lines
we assert on, that real NVML reports what the stub reports, or any timing of the
real stack. See docs/validation/TASK-025-026-027-loadout-gating.md.
"""

import asyncio
import importlib
import os
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

LM_DIR = Path(__file__).resolve().parents[1]
GIB = 1024 ** 3


# ── pynvml stub ──────────────────────────────────────────────────────────────

class NvmlConfig:
    """Mutable description of what the fake NVML should report."""

    def __init__(self):
        self.reset()

    def reset(self):
        # 4 x 24 GiB, all free: enough for every profile in profiles.yaml.
        self.devices = [{"total_gb": 24.0, "free_gb": 24.0} for _ in range(4)]
        self.init_error = None       # exception instance raised by nvmlInit
        self.memory_error = None     # exception instance raised by GetMemoryInfo


NVML = NvmlConfig()


def _build_pynvml_stub() -> types.ModuleType:
    m = types.ModuleType("pynvml")
    m.NVML_TEMPERATURE_GPU = 0

    def nvmlInit():
        if NVML.init_error is not None:
            raise NVML.init_error

    def nvmlShutdown():
        return None

    def nvmlDeviceGetCount():
        return len(NVML.devices)

    def nvmlDeviceGetHandleByIndex(i):
        return i

    def nvmlDeviceGetMemoryInfo(handle):
        if NVML.memory_error is not None:
            raise NVML.memory_error
        d = NVML.devices[handle]
        total = int(d["total_gb"] * GIB)
        free = int(d["free_gb"] * GIB)
        return SimpleNamespace(total=total, free=free, used=total - free)

    m.nvmlInit = nvmlInit
    m.nvmlShutdown = nvmlShutdown
    m.nvmlDeviceGetCount = nvmlDeviceGetCount
    m.nvmlDeviceGetHandleByIndex = nvmlDeviceGetHandleByIndex
    m.nvmlDeviceGetMemoryInfo = nvmlDeviceGetMemoryInfo
    m.nvmlDeviceGetUtilizationRates = lambda h: SimpleNamespace(gpu=0)
    m.nvmlDeviceGetTemperature = lambda h, kind: 40
    m.nvmlDeviceGetPowerUsage = lambda h: 100_000
    m.nvmlDeviceGetPciInfo = lambda h: SimpleNamespace(busId=b"0000:00:00.0")
    return m


def _build_docker_stub() -> None:
    docker = types.ModuleType("docker")
    errors = types.ModuleType("docker.errors")

    class DockerException(Exception):
        pass

    class NotFound(DockerException):
        pass

    class APIError(DockerException):
        pass

    errors.DockerException = DockerException
    errors.NotFound = NotFound
    errors.APIError = APIError
    docker.errors = errors
    docker.DockerClient = MagicMock()
    # api.services / api.stack call docker.from_env() at import and tolerate failure.
    docker.from_env = MagicMock(side_effect=DockerException("docker is stubbed in tests"))
    sys.modules["docker"] = docker
    sys.modules["docker.errors"] = errors


def _stub_if_missing(name: str) -> None:
    """Third-party deps that only api/* routers need; stub them if not installed."""
    try:
        importlib.import_module(name)
    except ImportError:
        sys.modules[name] = MagicMock(name=name)


# ── subprocess recorder ──────────────────────────────────────────────────────

class Call:
    """One recorded ``subprocess.run`` invocation."""

    START_VERBS = {"up", "start", "run", "create"}

    def __init__(self, seq, cmd, switching, active, on_loop):
        self.seq = seq
        self.cmd = [str(c) for c in cmd]
        self.switching = switching      # state["switching"] at call time
        self.active = active            # state["active_profile"] at call time
        self.on_loop = on_loop          # True => blocking call made on the event loop

    @property
    def verb(self):
        for v in ("up", "down", "start", "stop", "run", "create"):
            if v in self.cmd:
                return v
        return None

    @property
    def compose_files(self):
        out = []
        for i, a in enumerate(self.cmd):
            if a == "-f" and i + 1 < len(self.cmd):
                out.append(Path(self.cmd[i + 1]).name)
        return out

    @property
    def is_start(self):
        return self.cmd[:2] == ["docker", "compose"] and self.verb in self.START_VERBS

    @property
    def is_down(self):
        return self.cmd[:2] == ["docker", "compose"] and self.verb == "down"

    def __repr__(self):
        return f"Call#{self.seq}({' '.join(self.cmd)})"


class FakeDocker:
    """Replacement for subprocess.run. Records every call, never executes."""

    def __init__(self, main):
        self._main = main
        self.calls = []
        self.rules = []     # callables(Call) -> None | CompletedProcess | BaseException
        self.delay = 0.0    # seconds of *blocking* time.sleep per call

    def __call__(self, cmd, *args, **kwargs):
        try:
            asyncio.get_running_loop()
            on_loop = True
        except RuntimeError:
            on_loop = False
        st = self._main.state
        rec = Call(len(self.calls), cmd, st["switching"], st["active_profile"], on_loop)
        self.calls.append(rec)
        if self.delay:
            time.sleep(self.delay)
        for rule in self.rules:
            out = rule(rec)
            if out is None:
                continue
            if isinstance(out, BaseException):
                raise out
            return out
        if rec.verb == "up" and not rec.compose_files:
            # Modelled behaviour of `docker compose up` with no -f and no compose
            # file in cwd (documented docker behaviour; NOT verified on a host).
            return subprocess.CompletedProcess(cmd, 1, "", "no configuration file provided: not found")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    # convenience views
    @property
    def starts(self):
        return [c for c in self.calls if c.is_start]

    @property
    def downs(self):
        return [c for c in self.calls if c.is_down]

    def fail(self, verb, rc=1, stderr="boom"):
        def rule(c):
            if c.verb == verb:
                return subprocess.CompletedProcess(c.cmd, rc, "", stderr)
        self.rules.append(rule)

    def raise_on(self, verb, exc):
        def rule(c):
            if c.verb == verb:
                return exc
        self.rules.append(rule)


class FakeWS:
    """Stand-in for a connected /ws client; records pushed state events."""

    def __init__(self, fail=False):
        self.events = []
        self.fail = fail

    async def send_json(self, event):
        if self.fail:
            raise RuntimeError("peer gone")
        self.events.append(dict(event))


class _AsyncioProxy:
    """What ``main.asyncio`` is replaced with: real asyncio except ``sleep``."""

    def __init__(self, harness):
        self._h = harness

    def __getattr__(self, name):
        return getattr(asyncio, name)

    async def sleep(self, delay, *a, **kw):
        await self._h.sleep_hook(delay)

    def create_task(self, coro, *a, **kw):
        task = asyncio.create_task(coro, *a, **kw)
        self._h.tasks.append(task)
        return task


class Harness:
    def __init__(self, main, docker, ws, client):
        self.main = main
        self.docker = docker
        self.ws = ws
        self.client = client
        self.nvml = NVML
        self.profiles = main.load_profiles()
        self.sleeps = []
        self.tasks = []   # tasks main created via asyncio.create_task

        async def _noop(delay):
            self.sleeps.append(delay)
        self.sleep_hook = _noop

    # -- GPU telemetry
    def set_free(self, free_gb, total_gb=24.0):
        """Per-GPU free VRAM in GiB, e.g. set_free([5, 24, 24, 5])."""
        if isinstance(free_gb, (int, float)):
            free_gb = [free_gb] * 4
        NVML.devices = [{"total_gb": total_gb, "free_gb": f} for f in free_gb]

    def telemetry_down(self):
        NVML.init_error = RuntimeError("NVML Shared Library Not Found")

    # -- state helpers
    def make_active(self, name):
        p = self.profiles[name]
        self.main.state.update(
            active_profile=name, running_services=list(p["services"]),
            last_switched=1000.0, switching=False)

    def add_ws(self, fail=False):
        """Connect another fake /ws client; fail=True makes its sends raise."""
        ws = FakeWS(fail=fail)
        self.main._ws_clients.add(ws)
        return ws

    @property
    def state(self):
        return self.main.state

    def activate(self, name):
        return self.client.post(f"/activate/{name}")

    def snapshot(self):
        return dict(self.main.state)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def main_module():
    """Import loadout-manager/main.py once, with every host dependency stubbed."""
    tmp = tempfile.mkdtemp(prefix="loadout-tests-")
    os.environ["LOADOUT_STATE_PATH"] = str(Path(tmp) / "state.json")
    os.environ["LOADOUT_SCHEDULE_PATH"] = str(Path(tmp) / "schedule.json")
    os.environ.pop("KOVATI_OS_MODE", None)

    sys.modules["pynvml"] = _build_pynvml_stub()
    _build_docker_stub()
    for dep in ("psutil", "minio", "huggingface_hub"):
        _stub_if_missing(dep)

    sys.path.insert(0, str(LM_DIR))
    return importlib.import_module("main")


@pytest.fixture
def lm(main_module, monkeypatch, tmp_path):
    """Fresh, fully-mocked Loadout Manager harness for one test."""
    from fastapi.testclient import TestClient

    main = main_module
    NVML.reset()

    monkeypatch.delenv("KOVATI_OS_MODE", raising=False)
    monkeypatch.setattr(main, "STATE_PATH", tmp_path / "state.json")
    main.state.update(active_profile=None, switching=False,
                      last_switched=None, running_services=[])
    main._ws_clients.clear()

    docker = FakeDocker(main)
    monkeypatch.setattr(main.subprocess, "run", docker)

    ws = FakeWS()
    main._ws_clients.add(ws)

    # No lifespan context => the scheduler loop is NOT started by TestClient.
    client = TestClient(main.app)
    h = Harness(main, docker, ws, client)
    monkeypatch.setattr(main, "asyncio", _AsyncioProxy(h))

    yield h

    main._ws_clients.clear()
    NVML.reset()
    main.state.update(active_profile=None, switching=False,
                      last_switched=None, running_services=[])


# ── api/* router harness ─────────────────────────────────────────────────────

class FakeProc:
    """What a faked ``asyncio.create_subprocess_exec`` returns."""

    def __init__(self, rc, lines):
        self._rc = rc
        self._lines = [l if isinstance(l, bytes) else l.encode() for l in lines]
        self.returncode = None
        self.stdout = self

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for line in self._lines:
            yield line + b"\n"

    async def wait(self):
        self.returncode = self._rc
        return self._rc

    async def communicate(self, input=None):
        self.input = input.decode() if input else None
        self.returncode = self._rc
        return b"\n".join(self._lines), None

    def kill(self):
        pass


class FakeExec:
    """Replacement for asyncio.create_subprocess_exec. Records argv, never executes
    unless a test opts a command in with ``passthrough``."""

    def __init__(self, real):
        self._real = real
        self.calls = []
        self.procs = []   # (argv, FakeProc); FakeProc.input is what went to stdin
        self.rules = []   # callables(argv) -> None | (rc, lines)

    async def __call__(self, *argv, **kwargs):
        argv = [str(a) for a in argv]
        self.calls.append(argv)
        for rule in self.rules:
            out = rule(argv)
            if out == "passthrough":
                return await self._real(*argv, **kwargs)
            if out is not None:
                return self._keep(argv, FakeProc(*out))
        return self._keep(argv, FakeProc(0, []))

    def _keep(self, argv, proc):
        proc.input = None
        self.procs.append((argv, proc))
        return proc

    def on(self, predicate, rc=0, lines=(), effect=None):
        def rule(argv):
            if predicate(argv):
                if effect:
                    effect(argv)
                return rc, list(lines)
        self.rules.append(rule)

    def passthrough(self, predicate):
        self.rules.append(lambda argv: "passthrough" if predicate(argv) else None)

    def find(self, *words):
        return [c for c in self.calls if all(w in c for w in words)]


ENV_SAMPLE = """\
# Kovati docker/.env (test fixture)
GHCR_USER=octocat
GHCR_TOKEN=ghp_realtoken0000000000000000000000
HUGGINGFACE_TOKEN=hf_realtoken000000000000000000000000
WANDB_API_KEY=wandb0000000000000000000000000000000000
POSTGRES_ADMIN_PASSWORD=pg-admin-old
LANGFUSE_DB_PASSWORD=langfuse-db-old
LANGFUSE_NEXTAUTH_SECRET=nextauth-old
DIFY_DB_PASSWORD=dify-db-old
MINIO_ROOT_PASSWORD=minio-old
AUTHENTIK_SECRET_KEY=authentik-secret-old
KOVATI_OS_MODE=workstation
"""


@pytest.fixture
def api(lm, monkeypatch, tmp_path):
    """The api/* routers with every filesystem/process side effect redirected.

    * subprocess.run is already FakeDocker (via ``lm``; it patches the global).
    * asyncio.create_subprocess_exec is FakeExec (``api.exec``).
    * .env, the setup flag and BACKUP_ROOT live under tmp_path.
    * HOST_COMPOSE_DIR is set, so the backup helper has a repo path to mount.
    """
    from api import backup, secrets, setup

    env_file = tmp_path / "docker" / ".env"
    env_file.parent.mkdir()
    for mod in (secrets, setup):
        monkeypatch.setattr(mod, "ENV_FILE", env_file)
    monkeypatch.setattr(setup, "SETUP_COMPLETE_FLAG", tmp_path / "data" / ".kovati-setup-complete")

    data = tmp_path / "data"
    backups = data / "backups"
    backups.mkdir(parents=True)
    monkeypatch.setattr(backup, "BACKUP_ROOT", backups)
    monkeypatch.setattr(backup, "HOST_COMPOSE_DIR", "/srv/beta-workstation/docker")

    fake_exec = FakeExec(asyncio.create_subprocess_exec)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    return SimpleNamespace(
        client=lm.client, docker=lm.docker, exec=fake_exec,
        env_file=env_file, data=data, backups=backups, tmp=tmp_path,
        backup=backup, secrets=secrets, setup=setup)


@pytest.fixture
def async_client(lm):
    """httpx.AsyncClient bound to the app in-process (for concurrency tests)."""
    import httpx
    transport = httpx.ASGITransport(app=lm.main.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")
