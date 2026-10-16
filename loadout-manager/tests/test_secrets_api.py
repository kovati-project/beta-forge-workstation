"""
/api/secrets/* — listing and rotating values in docker/.env.

.env is a temp file seeded with ``ENV_SAMPLE``; service restarts go to FakeExec.

Defects are xfail(strict=True) so a fix fails the run until the marker goes.
"""

import re
from pathlib import Path

import pytest
import yaml

from conftest import ENV_SAMPLE

REPO = Path(__file__).resolve().parents[2]
SECRET_WORDS = ("PASSWORD", "SECRET", "KEY", "TOKEN", "SALT")


def _env(api):
    out = {}
    for line in api.env_file.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


@pytest.fixture
def seeded(api):
    api.env_file.write_text(ENV_SAMPLE)
    return api


# ── behaviour that is correct today ─────────────────────────────────────────

def test_list_returns_names_never_values(seeded):
    r = seeded.client.get("/api/secrets")
    assert r.status_code == 200
    keys = {s["key"] for s in r.json()["secrets"]}
    assert "POSTGRES_ADMIN_PASSWORD" in keys and "MINIO_ROOT_PASSWORD" in keys
    assert "GHCR_USER" not in keys and "KOVATI_OS_MODE" not in keys
    for value in _env(seeded).values():
        assert value not in r.text


def test_list_with_no_env_file_is_empty(api):
    assert api.client.get("/api/secrets").json() == {"secrets": []}


def test_rotate_changes_only_that_key_and_does_not_echo_it(seeded):
    before = seeded.env_file.read_text()
    r = seeded.client.post("/api/secrets/MINIO_ROOT_PASSWORD/rotate")
    assert r.status_code == 200
    after = _env(seeded)
    new = after["MINIO_ROOT_PASSWORD"]
    assert new != "minio-old" and re.fullmatch(r"[A-Za-z0-9_-]{43}", new)
    assert new not in r.text
    # every other line, comments included, is byte-for-byte unchanged
    old_lines = [l for l in before.splitlines() if not l.startswith("MINIO_ROOT_PASSWORD=")]
    new_lines = [l for l in seeded.env_file.read_text().splitlines()
                 if not l.startswith("MINIO_ROOT_PASSWORD=")]
    assert old_lines == new_lines


def test_rotate_unknown_key_is_refused_and_env_untouched(seeded):
    before = seeded.env_file.read_text()
    assert seeded.client.post("/api/secrets/NOT_A_KEY/rotate").status_code == 400
    assert seeded.env_file.read_text() == before
    assert seeded.exec.calls == []


def test_rotate_restarts_the_affected_services(seeded):
    seeded.client.post("/api/secrets/LANGFUSE_NEXTAUTH_SECRET/rotate")
    assert [c[-1] for c in seeded.exec.find("restart")] == ["langfuse"]


# ── defects ─────────────────────────────────────────────────────────────────

@pytest.mark.xfail(
    strict=True,
    reason="SEC-1: rotate-all picks keys by substring (KEY/TOKEN/...), so it "
           "overwrites third-party credentials it cannot rotate (HUGGINGFACE_TOKEN, "
           "WANDB_API_KEY, GHCR_TOKEN) with random strings, silently breaking model "
           "downloads, training logging and image pulls.")
def test_rotate_all_leaves_third_party_credentials_alone(seeded):
    before = _env(seeded)
    seeded.client.post("/api/secrets/rotate-all")
    after = _env(seeded)
    for k in ("HUGGINGFACE_TOKEN", "WANDB_API_KEY", "GHCR_TOKEN"):
        assert after[k] == before[k], k


@pytest.mark.xfail(
    strict=True,
    reason="SEC-2: rotating a database password rewrites .env only; the Postgres "
           "role keeps the old password, so the service fails auth on restart. "
           "This is the failure mode seen on the host (langfuse: Prisma P1000). "
           "Must either change the role (ALTER ROLE) or refuse.")
@pytest.mark.parametrize("key", ["LANGFUSE_DB_PASSWORD", "POSTGRES_ADMIN_PASSWORD"])
def test_db_password_rotation_updates_the_role_or_is_refused(seeded, key):
    r = seeded.client.post(f"/api/secrets/{key}/rotate")
    calls = seeded.exec.calls + [c.cmd for c in seeded.docker.calls]
    changed_role = any("ALTER ROLE" in " ".join(c).upper() for c in calls)
    assert r.status_code >= 400 or changed_role


@pytest.mark.xfail(
    strict=True,
    reason="SEC-3: restarts run `docker compose restart <svc>` with no -f / "
           "--project-directory, in the app's cwd, which holds no compose file; "
           "the restart fails (output discarded, process never awaited).")
def test_restart_targets_a_compose_project(seeded):
    seeded.client.post("/api/secrets/MINIO_ROOT_PASSWORD/rotate")
    (restart,) = seeded.exec.find("restart")
    assert "-f" in restart or "--project-directory" in restart


@pytest.mark.xfail(
    strict=True,
    reason="SEC-4: AFFECTS_MAP (the rotate allow-list) omits secrets that "
           "docker/.env.example defines and services need: AUTHENTIK_PG_PASSWORD, "
           "DIFY_DB_PASSWORD, WEBUI_SECRET_KEY cannot be rotated individually.")
def test_every_internal_secret_in_env_example_is_rotatable(seeded):
    from config import AFFECTS_MAP, CONFIG_SCHEMA_MAP
    example = (REPO / "docker" / ".env.example").read_text()
    keys = set(re.findall(r"^([A-Z0-9_]+)=", example, re.MULTILINE))
    internal = {k for k in keys if any(w in k for w in SECRET_WORDS)} - set(CONFIG_SCHEMA_MAP)
    assert internal - set(AFFECTS_MAP) == set()


@pytest.mark.xfail(
    strict=True,
    reason="SEC-5: every secret reports last_rotated '60d ago', a hard-coded "
           "placeholder. Unknown should be reported as unknown (null).")
def test_last_rotated_is_not_fabricated(seeded):
    for s in seeded.client.get("/api/secrets").json()["secrets"]:
        assert s["last_rotated"] != "60d ago"


@pytest.mark.xfail(
    strict=True,
    reason="SEC-6: the deployed container never sets ENV_FILE, so the default "
           "/home/kasemo/ai-workstation/docker/.env (a path that does not exist in "
           "the container) is used; docker/ is mounted at /compose read-only. "
           "/api/secrets lists nothing and rotation cannot write.")
def test_deployed_container_points_env_file_at_a_writable_env():
    svc = yaml.safe_load((REPO / "docker" / "compose.loadout.yml").read_text())
    lm = svc["services"]["loadout-manager"]
    env = dict(e.split("=", 1) for e in lm["environment"])
    assert "ENV_FILE" in env
    mount = next(v for v in lm["volumes"] if env["ENV_FILE"].startswith(v.split(":")[1]))
    assert not mount.endswith(":ro")
