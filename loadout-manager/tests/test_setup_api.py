"""
/api/setup/* — the first-boot wizard.

nvidia-smi and wg go through FakeDocker (``api.docker``; it records every
subprocess.run), NVML is the conftest stub, .env and the completion flag are
temp files.

Defects are xfail(strict=True) so a fix fails the run until the marker goes.
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
    ({"gpus": [{}] * 4, "nvlink_pairs": [[0, 3], [1, 2]], "total_vram_gb": 96}, "dual-stack"),
    ({"gpus": [{}] * 4, "nvlink_pairs": [], "total_vram_gb": 96}, "inference-4gpu"),
    ({"gpus": [{}] * 2, "nvlink_pairs": [[0, 1]], "total_vram_gb": 48}, "inference-pair-a"),
    ({"gpus": [{}] * 2, "nvlink_pairs": [], "total_vram_gb": 48}, "inference-pair-b"),
    ({"gpus": [{}], "nvlink_pairs": [], "total_vram_gb": 24}, "inference-small"),
    ({}, "inference-small"),
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


# ── defects ─────────────────────────────────────────────────────────────────

@pytest.mark.xfail(
    strict=True,
    reason="SET-1: generate-secrets writes key names nothing reads "
           "(POSTGRES_PASSWORD, LANGFUSE_SECRET_KEY, GRAFANA_ADMIN_PASSWORD, ...), "
           "while docker/.env.example, compose and config.SECRETS_REQUIRED use "
           "POSTGRES_ADMIN_PASSWORD, LANGFUSE_DB_PASSWORD, GF_ADMIN_PASSWORD, ... "
           "A wizard-provisioned box starts with every required secret missing.")
def test_generated_secrets_cover_every_required_secret(api):
    from config import SECRETS_REQUIRED
    required = {k for keys in SECRETS_REQUIRED.values() for k in keys}
    assert required - set(api.setup.SECRET_KEYS) == set()


@pytest.mark.xfail(
    strict=True,
    reason="SET-2: generate-secrets replaces the whole .env, discarding every "
           "other entry (GHCR_*, HUGGINGFACE_TOKEN, WANDB_API_KEY, KOVATI_OS_MODE).")
def test_generate_secrets_preserves_other_entries(api):
    api.env_file.write_text(ENV_SAMPLE)
    api.client.post("/api/setup/generate-secrets")
    env = _env(api)
    assert env.get("HUGGINGFACE_TOKEN", "").startswith("hf_")
    assert env.get("GHCR_USER") == "octocat"


@pytest.mark.xfail(
    strict=True,
    reason="SET-3: generate-secrets has no guard. After setup is complete it still "
           "replaces every live secret (databases keep the old ones), and the new "
           "values are returned in the response body.")
def test_generate_secrets_is_refused_after_setup_completes(api):
    api.client.post("/api/setup/complete")
    assert api.client.post("/api/setup/generate-secrets").status_code == 409


@pytest.mark.xfail(
    strict=True,
    reason="SET-4: the NVLink parser looks for 'X' (the Self diagonal) instead of "
           "NV# links and miscomputes indices; it finds no pairs on this "
           "workstation's real topology, so dual-stack is never recommended.")
def test_nvlink_pairs_parsed_from_real_topology(api):
    _reply(api, "nvidia-smi", stdout=TOPO_M)
    assert api.setup._detect_nvlink_pairs() == [[0, 3], [1, 2]]


@pytest.mark.xfail(
    strict=True,
    reason="SET-5: probe calls .decode() on nvmlDeviceGetName(); nvidia-ml-py>=12 "
           "(requirements.txt) returns str, so probe always fails with 500.")
def test_probe_with_modern_nvidia_ml_py(api, monkeypatch):
    import pynvml
    monkeypatch.setattr(pynvml, "nvmlDeviceGetName", lambda h: "NVIDIA GeForce RTX 3090",
                        raising=False)
    r = api.client.post("/api/setup/probe")
    assert r.status_code == 200, r.text
    assert len(r.json()["gpus"]) == len(NVML.devices)


@pytest.mark.xfail(
    strict=True,
    reason="SET-6: a failing `wg genkey` is not checked; setup/network reports "
           "success and writes an empty WIREGUARD_PUBKEY.")
def test_network_fails_when_wireguard_fails(api):
    _reply(api, "wg", rc=1)
    r = api.client.post("/api/setup/network")
    assert r.status_code >= 500
    assert "WIREGUARD_PUBKEY=" not in (api.env_file.read_text() if api.env_file.exists() else "")


@pytest.mark.xfail(
    strict=True,
    reason="SET-7: setup/validate checks nothing. It sleeps and prints a tick for "
           "each service, so it reports a fully healthy stack with nothing running.")
def test_validate_reports_failure_when_nothing_is_running(api, no_sleep):
    r = api.client.post("/api/setup/validate")
    assert "✓ Validation complete" not in r.text


@pytest.mark.xfail(
    strict=True,
    reason="SET-8: setup/provision pulls nothing. It sleeps and prints a tick per "
           "image (several not even used by this stack: authelia, node-red).")
def test_provision_actually_pulls_images(api, no_sleep):
    api.client.post("/api/setup/provision")
    calls = api.exec.calls + [c.cmd for c in api.docker.calls]
    assert any("pull" in c for c in calls)
