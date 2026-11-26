"""
WORKSTATION_HOST (#51): one value in docker/.env repoints every browser-facing
URL, so no compose file may hardcode the workstation's address, and the
loadout-manager's own compose calls must hand docker/.env to compose.
"""

import asyncio
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
COMPOSE_FILES = sorted((REPO / "docker").glob("compose.*.yml"))
DEFAULT = "${WORKSTATION_HOST:-10.10.10.2}"
IP = re.compile(r"\b(?:10\.10\.10|192\.168\.\d{1,3})\.\d{1,3}\b")


def test_compose_files_take_the_host_from_workstation_host():
    assert COMPOSE_FILES
    for path in COMPOSE_FILES:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            assert not IP.search(code.replace(DEFAULT, "")), f"{path.name}:{n}: {line.strip()}"


def test_env_example_defines_workstation_host():
    text = (REPO / "docker" / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^WORKSTATION_HOST=\S+", text, re.M)


def test_grafana_root_url_follows_workstation_host():
    doc = yaml.safe_load((REPO / "docker" / "compose.monitoring.yml").read_text(encoding="utf-8"))
    env = dict(e.split("=", 1) for e in doc["services"]["grafana"]["environment"])
    assert env["GF_SERVER_ROOT_URL"] == f"http://{DEFAULT}:3001/"


def test_service_compose_calls_pass_the_env_file(monkeypatch, tmp_path):
    from api import services

    env_file = tmp_path / ".env"
    env_file.write_text("WORKSTATION_HOST=kovati.lan\n")
    monkeypatch.setattr(services, "_ENV_FILE", env_file)
    calls = []

    class Proc:
        returncode = 0

        async def communicate(self):
            return b"", None

    async def fake_exec(*argv, **kwargs):
        calls.append(list(argv))
        return Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    rc, _ = asyncio.run(services._compose("compose.monitoring.yml", "up", "-d", "grafana"))
    assert rc == 0
    argv = calls[0]
    assert argv[argv.index("--env-file") + 1] == str(env_file)
    assert argv.index("--env-file") < argv.index("-f")
