"""
Opt-in API enforcement (#102): LOADOUT_REQUIRE_AUTH and LOADOUT_TRUSTED_PROXIES.

Off (the default) nothing changes. On, writes and sensitive reads need a valid
API key, or the Authentik identity header from a trusted proxy address.

The client address is set through TestClient(client=(host, port)), which is
what request.client.host reports; real Caddy-to-container traffic is not
exercised here.
"""

import json

import pytest
from fastapi.testclient import TestClient

CADDY_IP = "172.18.0.5"        # inside the default 172.16.0.0/12
LAN_IP = "192.168.1.50"        # a browser or script hitting :8800 directly


@pytest.fixture
def access(lm, monkeypatch, tmp_path):
    from api import access as access_mod
    from api import keys as keys_mod
    monkeypatch.setattr(keys_mod, "KEYS_FILE", str(tmp_path / "api_keys.json"))
    monkeypatch.setattr(access_mod, "ENV_FILE", tmp_path / ".env")
    for var in ("LOADOUT_REQUIRE_AUTH", "LOADOUT_TRUSTED_PROXIES", "KOVATI_OS_MODE"):
        monkeypatch.delenv(var, raising=False)
    access_mod.keys_path = tmp_path / "api_keys.json"
    return access_mod


@pytest.fixture
def enforce(access, monkeypatch):
    monkeypatch.setenv("LOADOUT_REQUIRE_AUTH", "true")
    return access


def _client(lm, host):
    return TestClient(lm.main.app, client=(host, 50000))


def _make_key(access, name="ci"):
    """Create a key directly in the store (the generate endpoint is itself protected)."""
    from api import keys as keys_mod
    raw = f"{keys_mod.KEY_PREFIX}test-{name}-0123456789abcdef"
    store = keys_mod._load_keys()
    store[name] = {"hash": keys_mod._hash(raw), "prefix": raw[:10],
                   "created": "2026-01-01T00:00:00Z", "last_used": None}
    keys_mod._save_keys(store)
    return raw


def _last_used(access, name="ci"):
    return json.loads(access.keys_path.read_text())[name]["last_used"]


# ── switch off ───────────────────────────────────────────────────────────────

def test_off_by_default(access):
    assert access.require_auth_enabled() is False


def test_off_everything_as_before(lm, access):
    assert lm.client.post("/stop").status_code == 200
    r = lm.client.post("/api/keys/generate", params={"name": "a"})
    assert r.status_code == 200
    assert lm.client.get("/api/keys").status_code == 200
    assert lm.client.delete("/api/keys/a").status_code == 200
    assert _client(lm, LAN_IP).post("/stop").status_code == 200


@pytest.mark.parametrize("value", ["false", "0", "no", "", "off"])
def test_off_values(access, monkeypatch, value):
    monkeypatch.setenv("LOADOUT_REQUIRE_AUTH", value)
    assert access.require_auth_enabled() is False


# ── switch on: no credentials ────────────────────────────────────────────────

@pytest.mark.parametrize("method,path", [
    ("POST", "/stop"),
    ("POST", "/activate/anything"),
    ("POST", "/api/keys/generate?name=x"),
    ("DELETE", "/api/keys/x"),
    ("POST", "/api/setup/complete"),
    ("GET", "/api/keys"),
    ("GET", "/api/secrets"),
    ("GET", "/api/config"),
    ("GET", "/api/backup/list"),
    ("GET", "/api/admin/anything"),
])
def test_on_no_credentials_401(lm, enforce, method, path):
    r = _client(lm, LAN_IP).request(method, path)
    assert r.status_code == 401, (method, path, r.text)
    assert "detail" in r.json()
    assert r.headers.get("www-authenticate") == "Bearer"


def test_on_401_does_not_reach_the_handler(lm, enforce):
    _client(lm, LAN_IP).post("/stop")
    assert lm.docker.calls == []


# ── switch on: API keys ──────────────────────────────────────────────────────

@pytest.mark.parametrize("header", ["bearer", "x-api-key"])
def test_on_valid_key_passes_and_touches(lm, enforce, header):
    raw = _make_key(enforce)
    headers = ({"Authorization": f"Bearer {raw}"} if header == "bearer"
               else {"X-API-Key": raw})
    assert _last_used(enforce) is None
    r = _client(lm, LAN_IP).post("/stop", headers=headers)
    assert r.status_code == 200, r.text
    assert _last_used(enforce) is not None
    assert _client(lm, LAN_IP).get("/api/keys", headers=headers).status_code == 200


def test_on_invalid_key_401(lm, enforce):
    _make_key(enforce)
    c = _client(lm, LAN_IP)
    assert c.post("/stop", headers={"X-API-Key": "nk_wrong"}).status_code == 401
    assert c.post("/stop", headers={"Authorization": "Bearer nk_wrong"}).status_code == 401
    assert c.post("/stop", headers={"Authorization": "Basic nk_wrong"}).status_code == 401
    assert _last_used(enforce) is None


def test_on_deleted_key_401(lm, enforce):
    raw = _make_key(enforce)
    c = _client(lm, LAN_IP)
    h = {"X-API-Key": raw}
    assert c.delete("/api/keys/ci", headers=h).status_code == 200
    assert c.post("/stop", headers=h).status_code == 401


# ── switch on: forward-auth identity ─────────────────────────────────────────

def test_on_identity_from_trusted_proxy_passes(lm, enforce):
    c = _client(lm, CADDY_IP)
    h = {"X-Authentik-Username": "alice"}
    assert c.post("/stop", headers=h).status_code == 200
    assert c.get("/api/keys", headers=h).status_code == 200


def test_on_identity_from_untrusted_source_ignored(lm, enforce):
    c = _client(lm, LAN_IP)
    h = {"X-Authentik-Username": "alice"}
    assert c.post("/stop", headers=h).status_code == 401
    assert c.get("/api/keys", headers=h).status_code == 401


def test_on_trusted_proxy_without_identity_401(lm, enforce):
    assert _client(lm, CADDY_IP).post("/stop").status_code == 401


def test_on_non_ip_client_is_untrusted(lm, enforce):
    # TestClient's default host is "testclient", which is not an address.
    assert lm.client.post("/stop", headers={"X-Authentik-Username": "alice"}).status_code == 401


def test_on_custom_trusted_proxies(lm, enforce, monkeypatch):
    monkeypatch.setenv("LOADOUT_TRUSTED_PROXIES", "10.9.0.0/24, not-a-cidr, fd00::/8")
    h = {"X-Authentik-Username": "alice"}
    assert _client(lm, "10.9.0.7").post("/stop", headers=h).status_code == 200
    assert _client(lm, "fd00::5").post("/stop", headers=h).status_code == 200
    assert _client(lm, CADDY_IP).post("/stop", headers=h).status_code == 401


# ── switch on: open routes ───────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["/status", "/loadouts", "/health", "/api/setup/status", "/"])
def test_on_read_only_gets_open(lm, enforce, path):
    assert _client(lm, LAN_IP).get(path).status_code == 200


def test_on_websocket_open(lm, enforce):
    with _client(lm, LAN_IP).websocket_connect("/ws") as ws:
        assert "active_profile" in json.dumps(ws.receive_json())


def test_on_monitoring_endpoints_open(lm, enforce):
    c = _client(lm, LAN_IP)
    # Neither route exists on every branch; what matters is that auth never blocks them.
    assert c.get("/metrics").status_code != 401
    assert c.post("/api/alerts/webhook", json={"alerts": []}).status_code != 401


def test_on_cors_preflight_open(lm, enforce):
    r = _client(lm, LAN_IP).options("/stop", headers={
        "Origin": "http://example", "Access-Control-Request-Method": "POST"})
    assert r.status_code != 401


# ── settings plumbing ────────────────────────────────────────────────────────

def test_switch_read_from_env_file(lm, access):
    access.ENV_FILE.write_text("LOADOUT_REQUIRE_AUTH=true\nLOADOUT_TRUSTED_PROXIES=10.1.0.0/16\n")
    assert access.require_auth_enabled() is True
    h = {"X-Authentik-Username": "alice"}
    assert _client(lm, LAN_IP).post("/stop").status_code == 401
    assert _client(lm, "10.1.2.3").post("/stop", headers=h).status_code == 200


def test_process_env_overrides_env_file(lm, access, monkeypatch):
    access.ENV_FILE.write_text("LOADOUT_REQUIRE_AUTH=true\n")
    monkeypatch.setenv("LOADOUT_REQUIRE_AUTH", "false")
    assert _client(lm, LAN_IP).post("/stop").status_code == 200


def test_settings_listed_in_config_schema():
    from config import CONFIG_SCHEMA_MAP
    for key in ("LOADOUT_REQUIRE_AUTH", "LOADOUT_TRUSTED_PROXIES"):
        assert CONFIG_SCHEMA_MAP[key]["category"] == "System"
        assert CONFIG_SCHEMA_MAP[key]["sensitive"] is False


def test_is_protected_policy(access):
    p = access.is_protected
    for m in ("POST", "PUT", "PATCH", "DELETE"):
        assert p(m, "/anything")
    assert not p("GET", "/status")
    assert not p("HEAD", "/loadouts")
    assert p("GET", "/api/secrets/x") and p("HEAD", "/api/config")
    assert not p("GET", "/api/metrics/gpu")
    assert not p("POST", "/api/alerts/webhook")
    assert not p("GET", "/metrics")
    assert not p("OPTIONS", "/stop")


# ── appliance mode ───────────────────────────────────────────────────────────

def test_appliance_mode_unchanged_when_off(lm, access, monkeypatch):
    monkeypatch.setenv("KOVATI_OS_MODE", "appliance")
    c = _client(lm, LAN_IP)
    assert c.get("/status").status_code == 401
    assert c.get("/status", headers={"X-Authentik-Username": "a"}).status_code == 200


def test_appliance_mode_uses_trust_model_when_on(lm, enforce, monkeypatch):
    monkeypatch.setenv("KOVATI_OS_MODE", "appliance")
    raw = _make_key(enforce)
    h = {"X-Authentik-Username": "a"}
    assert _client(lm, LAN_IP).get("/status", headers=h).status_code == 401
    assert _client(lm, CADDY_IP).get("/status", headers=h).status_code == 200
    assert _client(lm, LAN_IP).get("/status", headers={"X-API-Key": raw}).status_code == 200
    assert _client(lm, LAN_IP).post("/stop", headers={"X-API-Key": raw}).status_code == 200
