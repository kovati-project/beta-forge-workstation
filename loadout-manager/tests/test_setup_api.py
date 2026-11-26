"""
/api/setup/* — the first-boot wizard.

nvidia-smi and wg go through FakeDocker (``api.docker``; it records every
subprocess.run), NVML is the conftest stub, .env and the completion flag are
temp files.

SET-4..SET-8 were strict xfails documenting defects; they are plain tests now.
"""

import re
import subprocess
from pathlib import Path

import pytest
import yaml

from conftest import ENV_SAMPLE, NVML

REPO = Path(__file__).resolve().parents[2]

# `nvidia-smi topo -m` on this workstation: NVLink bridges GPU0<->GPU3 (pair A)
# and GPU1<->GPU2 (pair B); see main.py and configs/drivers/verify-drivers.sh.
TOPO_M = """\
\tGPU0\tGPU1\tGPU2\tGPU3\tCPU Affinity\tNUMA Affinity\tGPU NUMA ID
GPU0\t X \tSYS\tSYS\tNV4\t0-31\t0\t\tN/A
GPU1\tSYS\t X \tNV4\tSYS\t0-31\t0\t\tN/A
GPU2\tSYS\tNV4\t X \tSYS\t0-31\t0\t\tN/A
GPU3\tNV4\tSYS\tSYS\t X \t0-31\t0\t\tN/A

Legend:

  X    = Self
  SYS  = Connection traversing PCIe as well as the SMP interconnect between NUMA nodes
  NV#  = Connection traversing a bonded set of # NVLinks
"""


def _env(api):
    return dict(l.split("=", 1) for l in api.env_file.read_text().splitlines()
                if l and not l.startswith("#") and "=" in l)


def _reply(api, prog, stdout="", rc=0):
    def rule(c):
        if c.cmd and c.cmd[0] == prog:
            return subprocess.CompletedProcess(c.cmd, rc, stdout, "")
    api.docker.rules.append(rule)


@pytest.fixture
def no_sleep(api, monkeypatch):
    import asyncio
    import types

    async def instant(*_a, **_k):
        return None
    proxy = types.SimpleNamespace(**{k: getattr(asyncio, k) for k in dir(asyncio)
                                     if not k.startswith("__")})
    proxy.sleep = instant
    monkeypatch.setattr(api.setup, "asyncio", proxy)


# ── behaviour that is correct today ─────────────────────────────────────────

def test_completion_flag_lifecycle(api):
    assert api.client.get("/api/setup/status").json()["complete"] is False
    assert api.client.post("/api/setup/complete").json() == {"status": "complete"}
    assert api.client.get("/api/setup/status").json()["complete"] is True
    assert api.client.delete("/api/setup/completion-flag").status_code == 200
    assert api.client.get("/api/setup/status").json()["complete"] is False


@pytest.mark.parametrize("hardware, expected", [
    ({"gpus": [{}] * 4, "nvlink_pairs": [[0, 3], [1, 2]], "total_vram_gb": 96}, "inference-4gpu"),
    ({"gpus": [{}] * 4, "nvlink_pairs": [], "total_vram_gb": 96}, "inference-4gpu"),
    ({"gpus": [{}] * 2, "nvlink_pairs": [[0, 1]], "total_vram_gb": 48}, "inference-pair-a"),
    ({"gpus": [{}] * 2, "nvlink_pairs": [], "total_vram_gb": 48}, "inference-pair-b"),
    ({"gpus": [{}], "nvlink_pairs": [], "total_vram_gb": 24}, "idle"),
    ({}, "idle"),
])
def test_recommendation(api, hardware, expected):
    r = api.client.post("/api/setup/recommend", json=hardware)
    assert r.status_code == 200 and r.json()["recommended"] == expected


def test_every_recommendation_is_a_real_profile(api, lm):
    import inspect
    src = inspect.getsource(api.setup.recommend_profile)
    for name in re.findall(r'profile = "([a-z0-9-]+)"', src):
        assert name in lm.profiles, name


def test_generate_secrets_writes_strong_unique_values(api):
    body = api.client.post("/api/setup/generate-secrets").json()
    env = _env(api)
    assert set(body["keys"]) == set(env)
    assert len(set(env.values())) == len(env)
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{43}", v) for v in env.values())


def test_network_keeps_existing_entries_and_stores_pubkey(api):
    api.env_file.write_text(ENV_SAMPLE)
    _reply(api, "wg", stdout="wg-key-material\n")
    r = api.client.post("/api/setup/network", params={"jumpbox_ip": "10.9.9.1"})
    assert r.status_code == 200
    env = _env(api)
    assert env["JUMPBOX_IP"] == "10.9.9.1" and env["WIREGUARD_PUBKEY"] == "wg-key-material"
    assert env["HUGGINGFACE_TOKEN"].startswith("hf_")


def test_generated_secrets_cover_every_required_secret():
    from config import GENERATED_SECRETS, SECRETS_REQUIRED
    required = {k for keys in SECRETS_REQUIRED.values() for k in keys}
    assert required - set(GENERATED_SECRETS) == set()


def test_generated_secrets_match_init_secrets_sh():
    """The wizard and scripts/init-secrets.sh must produce the same key set."""
    from config import GENERATED_SECRETS
    script = (REPO / "scripts" / "init-secrets.sh").read_text(encoding="utf-8")
    generated_by_script = set(re.findall(r"^([A-Z0-9_]+)=\$\(gen", script, re.MULTILINE))
    assert generated_by_script == set(GENERATED_SECRETS)
    assert "N8N_ENCRYPTION_KEY" not in GENERATED_SECRETS  # n8n owns its own key


def test_generate_secrets_preserves_other_entries(api):
    api.env_file.write_text(ENV_SAMPLE)
    api.client.post("/api/setup/generate-secrets")
    text = api.env_file.read_text()
    assert text.startswith(ENV_SAMPLE)          # untouched, comments included
    env = _env(api)
    assert env["HUGGINGFACE_TOKEN"].startswith("hf_") and env["GHCR_USER"] == "octocat"


def test_generate_secrets_never_replaces_an_existing_value(api):
    api.env_file.write_text(ENV_SAMPLE)
    body = api.client.post("/api/setup/generate-secrets").json()
    env = _env(api)
    assert env["POSTGRES_ADMIN_PASSWORD"] == "pg-admin-old"
    assert "POSTGRES_ADMIN_PASSWORD" in body["kept"]
    assert "POSTGRES_ADMIN_PASSWORD" not in body["secrets"]
    assert "pg-admin-old" not in str(body)


def test_generate_secrets_is_idempotent(api):
    api.client.post("/api/setup/complete")
    first = api.client.post("/api/setup/generate-secrets").json()
    snapshot = api.env_file.read_text()
    second = api.client.post("/api/setup/generate-secrets").json()
    assert first["keys"] and second["keys"] == [] and second["secrets"] == {}
    assert api.env_file.read_text() == snapshot


def test_generate_secrets_fills_empty_values(api):
    api.env_file.write_text("LANGFUSE_DB_PASSWORD=\nGHCR_USER=octocat\n")
    body = api.client.post("/api/setup/generate-secrets").json()
    assert "LANGFUSE_DB_PASSWORD" in body["keys"]
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", _env(api)["LANGFUSE_DB_PASSWORD"])
    assert api.env_file.read_text().count("LANGFUSE_DB_PASSWORD=") == 1


# ── formerly defects (SET-4..SET-8) ─────────────────────────────────────────

# SET-4 (fixed)
def test_nvlink_pairs_parsed_from_real_topology(api):
    _reply(api, "nvidia-smi", stdout=TOPO_M)
    assert api.setup._detect_nvlink_pairs() == [[0, 3], [1, 2]]


# SET-5 (fixed)
def test_probe_with_modern_nvidia_ml_py(api, monkeypatch):
    import pynvml
    monkeypatch.setattr(pynvml, "nvmlDeviceGetName", lambda h: "NVIDIA GeForce RTX 3090",
                        raising=False)
    r = api.client.post("/api/setup/probe")
    assert r.status_code == 200, r.text
    assert len(r.json()["gpus"]) == len(NVML.devices)


# SET-6 (fixed)
def test_network_fails_when_wireguard_fails(api):
    _reply(api, "wg", rc=1)
    r = api.client.post("/api/setup/network")
    assert r.status_code >= 500
    assert "WIREGUARD_PUBKEY=" not in (api.env_file.read_text() if api.env_file.exists() else "")


# SET-7 (fixed)
def test_validate_reports_failure_when_nothing_is_running(api, no_sleep):
    r = api.client.post("/api/setup/validate")
    assert "✓ Validation complete" not in r.text


# SET-8 (fixed)
def test_provision_actually_pulls_images(api, no_sleep):
    api.client.post("/api/setup/provision")
    calls = api.exec.calls + [c.cmd for c in api.docker.calls]
    assert any("pull" in c for c in calls)


# ── network ─────────────────────────────────────────────────────────────────

def test_network_accepts_the_json_body_the_wizard_sends(api):
    api.env_file.write_text(ENV_SAMPLE)
    _reply(api, "wg", stdout="wg-key-material\n")
    r = api.client.post("/api/setup/network",
                        json={"jumpbox_ip": "10.8.0.1", "enable_caddy": False})
    assert r.status_code == 200, r.text
    env = _env(api)
    assert env["JUMPBOX_IP"] == "10.8.0.1" and env["CADDY_ENABLED"] == "false"
    assert api.env_file.read_text().startswith(ENV_SAMPLE)  # comments, order kept


@pytest.mark.parametrize("bad", ["10.0.0.1\nPOSTGRES_ADMIN_PASSWORD=x", "not-an-ip", "10.0.0.256"])
def test_network_rejects_a_non_ip_and_writes_nothing(api, bad):
    api.env_file.write_text(ENV_SAMPLE)
    _reply(api, "wg", stdout="wg-key-material\n")
    r = api.client.post("/api/setup/network", json={"jumpbox_ip": bad})
    assert r.status_code == 400
    assert api.env_file.read_text() == ENV_SAMPLE
    assert not [c for c in api.docker.calls if c.cmd and c.cmd[0] == "wg"]


def test_network_does_not_invent_a_lan_ip(api):
    api.env_file.write_text(ENV_SAMPLE)
    _reply(api, "wg", stdout="wg-key-material\n")
    api.client.post("/api/setup/network", json={"jumpbox_ip": "10.8.0.1"})
    assert "KOVATI_OS_LAN_IP" not in _env(api)
    api.client.post("/api/setup/network", json={"jumpbox_ip": "10.8.0.1", "lan_ip": "192.168.1.20"})
    assert _env(api)["KOVATI_OS_LAN_IP"] == "192.168.1.20"


def test_network_keeps_the_private_key_out_of_env_at_0600_and_reuses_it(api):
    import stat
    _reply(api, "wg", stdout="wg-key-material\n")
    assert api.client.post("/api/setup/network", json={}).status_code == 200
    key = api.setup._wg_key_file()
    assert key.read_text().strip() == "wg-key-material"
    assert stat.S_IMODE(key.stat().st_mode) == 0o600
    genkeys = lambda: [c for c in api.docker.calls if c.cmd[:2] == ["wg", "genkey"]]
    assert len(genkeys()) == 1
    api.client.post("/api/setup/network", json={})
    assert len(genkeys()) == 1, "a re-run must not rotate the tunnel key"


# ── provision / validate ────────────────────────────────────────────────────

def _sse_lines(text):
    return [l[len("data: "):] for l in text.splitlines() if l.startswith("data: ")]


def test_provision_pulls_every_stack_including_profiled_services(api, no_sleep):
    lines = _sse_lines(api.client.post("/api/setup/provision").text)
    pulls = api.exec.find("pull")
    files = api.setup._stack_files()
    assert files and len(pulls) == len(files)
    for argv in pulls:
        assert "--ignore-buildable" in argv
        assert argv[argv.index("--profile") + 1] == "*"
    assert lines[-1] == "✓ All images provisioned"
    assert f"Progress: {len(files)}/{len(files)}" in lines


def test_provision_reports_a_failed_pull(api, no_sleep):
    api.exec.on(lambda argv: "pull" in argv and any(a.endswith("compose.storage.yml") for a in argv),
                rc=1, lines=["manifest unknown"])
    lines = _sse_lines(api.client.post("/api/setup/provision").text)
    assert "✗ compose.storage.yml: manifest unknown" in lines
    assert "✓ All images provisioned" not in lines
    assert lines[-1].startswith("✗ 1 of ")


def _compose_file_of(argv):
    return next(Path(a).name for i, a in enumerate(argv) if i and argv[i - 1] == "-f")


def _healthy_stack(api):
    import json as _json
    from api import secrets as secrets_api

    def services(cf):
        doc = yaml.safe_load((secrets_api.COMPOSE_DIR / cf).read_text())
        return [n for n, s in doc["services"].items() if not (s or {}).get("profiles")]

    def rule(argv):
        if "config" in argv:
            return 0, services(_compose_file_of(argv))
        if "ps" in argv:
            return 0, [_json.dumps({"Service": s, "State": "running", "Health": ""})
                       for s in services(_compose_file_of(argv))]
    api.exec.rules.append(rule)


def test_validate_passes_when_secrets_are_set_and_core_services_run(api, no_sleep):
    api.client.post("/api/setup/generate-secrets")
    _healthy_stack(api)
    lines = _sse_lines(api.client.post("/api/setup/validate").text)
    assert lines[-1] == "✓ Validation complete", lines
    assert not [l for l in lines if l.startswith("✗")]


def test_validate_names_an_unhealthy_service(api, no_sleep):
    import json as _json
    api.client.post("/api/setup/generate-secrets")

    def unhealthy(argv):
        if "ps" in argv and _compose_file_of(argv) == "compose.storage.yml":
            return 0, [_json.dumps({"Service": "qdrant", "State": "running", "Health": "unhealthy"})]
    api.exec.rules.append(unhealthy)
    _healthy_stack(api)
    lines = _sse_lines(api.client.post("/api/setup/validate").text)
    assert "✗ qdrant: unhealthy" in lines
    assert any(l.endswith(": not created") for l in lines)  # the rest of storage is absent
    assert lines[-1].startswith("✗ Validation failed")


def test_validate_requires_the_generated_secrets(api, no_sleep):
    _healthy_stack(api)
    lines = _sse_lines(api.client.post("/api/setup/validate").text)
    assert any(l.startswith("✗ Secrets") for l in lines)
    assert lines[-1].startswith("✗ Validation failed")


def test_ps_json_array_and_ndjson_parse_the_same():
    import json as _json
    from api import setup
    rows = [{"Service": "a", "State": "running"}, {"Service": "b", "State": "exited"}]
    assert setup._parse_ps(_json.dumps(rows)) == setup._parse_ps(
        "\n".join(_json.dumps(r) for r in rows)) == {"a": rows[0], "b": rows[1]}
