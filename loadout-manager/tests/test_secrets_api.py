"""
/api/secrets/* — listing and rotating platform-managed values in docker/.env.

.env is a temp file seeded with ``ENV_SAMPLE``; psql and docker compose go to
FakeExec. What this can NOT prove: that real psql/compose accept these command
lines, or how a real consumer behaves on recreate. See
docs/runbooks/rotate-postgres-passwords.md for the procedure this mirrors.

Remaining defects are xfail(strict=True) so a fix fails the run until the
marker goes.
"""

import re
from pathlib import Path

import pytest
import yaml

from conftest import ENV_SAMPLE

REPO = Path(__file__).resolve().parents[2]
SECRET_WORDS = ("PASSWORD", "SECRET", "KEY", "TOKEN", "SALT")
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")


def _env(api):
    out = {}
    for line in api.env_file.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def _is_psql(container=None):
    return lambda a: a[:2] == ["docker", "exec"] and "psql" in a and (
        container is None or container in a)


def _running(api, *services):
    """compose ps reports these services as running (others: not running)."""
    api.exec.on(lambda a: "ps" in a and a[-1] in services, lines=["c0ffee"])


def _alters(api):
    return [(argv, proc.input) for argv, proc in api.exec.procs if "psql" in argv]


@pytest.fixture
def seeded(api):
    api.env_file.write_text(ENV_SAMPLE)
    return api


# ── listing ─────────────────────────────────────────────────────────────────

def test_list_returns_managed_names_never_values(seeded):
    r = seeded.client.get("/api/secrets")
    assert r.status_code == 200
    keys = {s["key"] for s in r.json()["secrets"]}
    assert {"POSTGRES_ADMIN_PASSWORD", "MINIO_ROOT_PASSWORD"} <= keys
    # third-party credentials and plain config are not "secrets" the platform owns
    assert not keys & {"GHCR_USER", "GHCR_TOKEN", "HUGGINGFACE_TOKEN", "WANDB_API_KEY",
                       "KOVATI_OS_MODE"}
    for value in _env(seeded).values():
        assert value not in r.text


def test_list_marks_non_rotatable_secrets(seeded):
    by_key = {s["key"]: s for s in seeded.client.get("/api/secrets").json()["secrets"]}
    assert by_key["MINIO_ROOT_PASSWORD"]["rotatable"] is True
    assert by_key["AUTHENTIK_SECRET_KEY"]["rotatable"] is False
    assert by_key["AUTHENTIK_SECRET_KEY"]["note"]


def test_last_rotated_is_not_fabricated(seeded):
    for s in seeded.client.get("/api/secrets").json()["secrets"]:
        assert s["last_rotated"] is None


def test_list_with_no_env_file_is_empty(api):
    assert api.client.get("/api/secrets").json() == {"secrets": []}


# ── rotating one secret ─────────────────────────────────────────────────────

def test_rotate_changes_only_that_key_and_does_not_echo_it(seeded):
    before = seeded.env_file.read_text()
    r = seeded.client.post("/api/secrets/MINIO_ROOT_PASSWORD/rotate")
    assert r.status_code == 200 and r.json()["status"] == "rotated"
    new = _env(seeded)["MINIO_ROOT_PASSWORD"]
    assert new != "minio-old" and TOKEN.fullmatch(new)
    assert new not in r.text
    # every other line, comments included, is byte-for-byte unchanged
    def others(text):
        return [l for l in text.splitlines() if not l.startswith("MINIO_ROOT_PASSWORD=")]
    assert others(before) == others(seeded.env_file.read_text())


def test_rotate_unknown_key_is_refused_and_env_untouched(seeded):
    before = seeded.env_file.read_text()
    assert seeded.client.post("/api/secrets/NOT_A_KEY/rotate").status_code == 400
    assert seeded.env_file.read_text() == before
    assert seeded.exec.calls == []


@pytest.mark.parametrize("key", ["HUGGINGFACE_TOKEN", "GHCR_TOKEN", "N8N_ENCRYPTION_KEY"])
def test_third_party_and_self_managed_keys_cannot_be_rotated(seeded, key):
    before = seeded.env_file.read_text()
    assert seeded.client.post(f"/api/secrets/{key}/rotate").status_code == 400
    assert seeded.env_file.read_text() == before


@pytest.mark.parametrize("key", ["AUTHENTIK_SECRET_KEY", "DIFY_SECRET_KEY", "GF_ADMIN_PASSWORD"])
def test_non_rotatable_secret_is_refused_with_reason(seeded, key):
    before = seeded.env_file.read_text()
    r = seeded.client.post(f"/api/secrets/{key}/rotate")
    assert r.status_code == 409 and "cannot be rotated" in r.json()["detail"]
    assert seeded.env_file.read_text() == before
    assert seeded.exec.calls == []


def test_rotate_without_env_file_is_503(api):
    assert api.client.post("/api/secrets/MINIO_ROOT_PASSWORD/rotate").status_code == 503
    assert not api.env_file.exists()


def test_running_consumers_are_recreated_not_restarted(seeded):
    _running(seeded, "langfuse")
    r = seeded.client.post("/api/secrets/LANGFUSE_NEXTAUTH_SECRET/rotate")
    assert r.json()["services"] == [{"service": "langfuse", "status": "recreated"}]
    assert seeded.exec.find("restart") == []
    (up,) = seeded.exec.find("up")
    assert up[-4:] == ["-d", "--no-deps", "--force-recreate", "langfuse"]
    assert ["--env-file", str(seeded.env_file)] == up[up.index("--env-file"):up.index("--env-file") + 2]
    assert up[up.index("-f") + 1].endswith("compose.storage.yml")


def test_stopped_consumers_are_not_started(seeded):
    r = seeded.client.post("/api/secrets/MINIO_ROOT_PASSWORD/rotate")
    assert r.json()["services"] == [{"service": "minio", "status": "not running"}]
    assert seeded.exec.find("up") == []


def test_failed_recreate_is_reported_as_partial(seeded):
    _running(seeded, "minio")
    seeded.exec.on(lambda a: "up" in a, rc=1, lines=["Error response from daemon: boom"])
    body = seeded.client.post("/api/secrets/MINIO_ROOT_PASSWORD/rotate").json()
    assert body["status"] == "partial"
    assert body["services"][0]["status"] == "error" and "boom" in body["services"][0]["detail"]


# ── database passwords ──────────────────────────────────────────────────────

def test_db_password_rotation_alters_the_role_before_touching_env(seeded):
    seen_env_at_alter = []
    seeded.exec.on(_is_psql(), effect=lambda a: seen_env_at_alter.append(
        _env(seeded)["LANGFUSE_DB_PASSWORD"]))
    _running(seeded, "langfuse")

    r = seeded.client.post("/api/secrets/LANGFUSE_DB_PASSWORD/rotate")
    assert r.status_code == 200 and r.json()["status"] == "rotated"
    new = _env(seeded)["LANGFUSE_DB_PASSWORD"]

    ((argv, sql),) = _alters(seeded)
    assert argv[:4] == ["docker", "exec", "-i", "postgres"]
    assert sql.strip() == f"ALTER ROLE \"langfuse\" WITH PASSWORD '{new}';"
    assert new not in " ".join(argv), "password must go on stdin, not argv"
    assert seen_env_at_alter == ["langfuse-db-old"]       # role changed first
    assert seeded.exec.find("--force-recreate", "langfuse")  # then consumer recreated


def test_failed_alter_role_leaves_env_and_services_alone(seeded):
    before = seeded.env_file.read_text()
    _running(seeded, "langfuse")
    seeded.exec.on(_is_psql(), rc=2, lines=['psql: error: role "langfuse" does not exist'])
    r = seeded.client.post("/api/secrets/LANGFUSE_DB_PASSWORD/rotate")
    assert r.status_code == 502 and "does not exist" in r.json()["detail"]
    assert seeded.env_file.read_text() == before
    assert seeded.exec.find("up") == []


def test_second_instance_failure_reverts_the_first(seeded):
    """DIFY_DB_PASSWORD lives in the shared postgres AND dify-db."""
    seeded.exec.on(_is_psql("dify-db"), rc=2, lines=["connection refused"])
    before = seeded.env_file.read_text()
    r = seeded.client.post("/api/secrets/DIFY_DB_PASSWORD/rotate")
    assert r.status_code == 502
    assert seeded.env_file.read_text() == before
    statements = [(a[3], sql) for a, sql in _alters(seeded)]
    assert [c for c, _ in statements] == ["postgres", "dify-db", "postgres"]
    assert "'dify-db-old'" in statements[-1][1]          # shared role put back


def test_failed_revert_is_reported(seeded):
    seeded.exec.on(_is_psql("dify-db"), rc=2, lines=["connection refused"])
    calls = {"n": 0}

    def second_shared_call_fails(a):
        if _is_psql("postgres")(a) and "dify-db" not in a:
            calls["n"] += 1
            return calls["n"] == 2
    seeded.exec.on(second_shared_call_fails, rc=2, lines=["server closed the connection"])
    detail = seeded.client.post("/api/secrets/DIFY_DB_PASSWORD/rotate").json()["detail"]
    assert "could NOT restore role dify in postgres" in detail


# ── rotate-all ──────────────────────────────────────────────────────────────

def test_rotate_all_rotates_only_rotatable_managed_secrets(seeded):
    before = _env(seeded)
    body = seeded.client.post("/api/secrets/rotate-all").json()
    after = _env(seeded)
    for k in ("HUGGINGFACE_TOKEN", "WANDB_API_KEY", "GHCR_TOKEN", "GHCR_USER",
              "KOVATI_OS_MODE", "AUTHENTIK_SECRET_KEY"):
        assert after[k] == before[k], k
    rotated = {"POSTGRES_ADMIN_PASSWORD", "LANGFUSE_DB_PASSWORD", "LANGFUSE_NEXTAUTH_SECRET",
               "DIFY_DB_PASSWORD", "MINIO_ROOT_PASSWORD"}
    assert set(body["rotated"]) == rotated
    assert all(after[k] != before[k] and TOKEN.fullmatch(after[k]) for k in rotated)
    assert [s["key"] for s in body["skipped"]] == ["AUTHENTIK_SECRET_KEY"]
    assert body["status"] == "rotated"


def test_rotate_all_recreates_each_consumer_once(seeded):
    _running(seeded, "langfuse", "minio", "dify-api")
    body = seeded.client.post("/api/secrets/rotate-all").json()
    assert sorted(s["service"] for s in body["services"]) == ["dify-api", "langfuse", "minio"]
    assert len(seeded.exec.find("--force-recreate", "langfuse")) == 1


def test_rotate_all_continues_past_a_failure(seeded):
    seeded.exec.on(_is_psql("dify-db"), rc=2, lines=["connection refused"])
    before = _env(seeded)
    body = seeded.client.post("/api/secrets/rotate-all").json()
    assert body["status"] == "partial"
    assert [f["key"] for f in body["failed"]] == ["DIFY_DB_PASSWORD"]
    assert _env(seeded)["DIFY_DB_PASSWORD"] == before["DIFY_DB_PASSWORD"]
    assert _env(seeded)["MINIO_ROOT_PASSWORD"] != before["MINIO_ROOT_PASSWORD"]


# ── configuration consistency ───────────────────────────────────────────────

def test_every_internal_secret_in_env_example_is_managed():
    from config import MANAGED_SECRETS, CONFIG_SCHEMA_MAP
    example = (REPO / "docker" / ".env.example").read_text(encoding="utf-8")
    keys = set(re.findall(r"^([A-Z0-9_]+)=", example, re.MULTILINE))
    internal = {k for k in keys if any(w in k for w in SECRET_WORDS)} - set(CONFIG_SCHEMA_MAP)
    assert internal - set(MANAGED_SECRETS) == set()


def test_managed_secret_consumers_exist_in_compose():
    from config import MANAGED_SECRETS
    for key, spec in MANAGED_SECRETS.items():
        for compose_file, service in spec["recreate"]:
            doc = yaml.safe_load((REPO / "docker" / compose_file).read_text(encoding="utf-8"))
            assert service in doc["services"], (key, compose_file, service)
            assert f"${{{key}}}" in str(doc["services"][service]), (key, service)


def test_deployed_container_points_env_file_at_a_writable_env():
    svc = yaml.safe_load((REPO / "docker" / "compose.loadout.yml").read_text(encoding="utf-8"))
    lm = svc["services"]["loadout-manager"]
    env = dict(e.split("=", 1) for e in lm["environment"])
    mount = next(v for v in lm["volumes"]
                 if isinstance(v, dict) and v["target"] == env["ENV_FILE"])
    assert mount["source"] == "./.env" and not mount.get("read_only")
    assert mount["bind"]["create_host_path"] is False
