"""
API key lifecycle (TASK-113, #61): generate / list / touch / delete.

Checks that the key is returned exactly once, never stored or listed in the
clear, persisted with mode 0600, and that old plaintext stores are upgraded.

Not covered: enforcement. No endpoint checks API keys today; verify_api_key()
exists for when one does.
"""

import asyncio
import json
import os
import stat
import sys
import threading

import pytest


@pytest.fixture
def keys(lm, monkeypatch, tmp_path):
    from api import keys as keys_mod
    path = tmp_path / "loadout-manager" / "api_keys.json"
    monkeypatch.setattr(keys_mod, "KEYS_FILE", str(path))
    keys_mod.path = path
    return keys_mod


def _generate(lm, name):
    return lm.client.post("/api/keys/generate", params={"name": name})


def test_default_store_is_on_the_persisted_volume(lm):
    from api import keys as keys_mod
    if not os.getenv("API_KEYS_FILE"):
        assert keys_mod.KEYS_FILE.startswith("/data/loadout-manager/")


def test_full_cycle(lm, keys):
    r = _generate(lm, "ci-runner")
    assert r.status_code == 200, r.text
    key = r.json()["key"]
    assert key.startswith("nk_") and len(key) > 40

    listed = lm.client.get("/api/keys").json()
    assert listed["count"] == 1
    entry = listed["keys"][0]
    assert entry["name"] == "ci-runner"
    assert entry["prefix"] == key[:10] + "..."
    assert entry["last_used"] is None
    assert key not in json.dumps(listed)

    r = lm.client.post("/api/keys/ci-runner/touch")
    assert r.status_code == 200 and r.json()["last_used"]
    assert lm.client.get("/api/keys").json()["keys"][0]["last_used"] == r.json()["last_used"]

    assert lm.client.delete("/api/keys/ci-runner").json() == {"status": "deleted", "name": "ci-runner"}
    assert lm.client.get("/api/keys").json() == {"keys": [], "count": 0}
    assert lm.client.delete("/api/keys/ci-runner").status_code == 404
    assert lm.client.post("/api/keys/ci-runner/touch").status_code == 404


def test_raw_key_is_never_stored(lm, keys):
    key = _generate(lm, "a").json()["key"]
    on_disk = keys.path.read_text()
    assert key not in on_disk
    assert key[10:] not in on_disk
    assert json.loads(on_disk)["a"]["hash"] == keys._hash(key)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_store_is_private(lm, keys):
    _generate(lm, "a")
    assert stat.S_IMODE(keys.path.stat().st_mode) == 0o600


def test_duplicate_name_is_rejected(lm, keys):
    assert _generate(lm, "dup").status_code == 200
    assert _generate(lm, "dup").status_code == 409


@pytest.mark.parametrize("name", ["", "has space", "../escape", "a/b", "-lead", "x" * 65])
def test_invalid_names_are_rejected(lm, keys, name):
    assert _generate(lm, name).status_code in (400, 404, 405, 422)
    assert lm.client.get("/api/keys").json()["count"] == 0


def test_verify_api_key(lm, keys):
    key = _generate(lm, "svc").json()["key"]
    assert keys.verify_api_key(key) == "svc"
    assert lm.client.get("/api/keys").json()["keys"][0]["last_used"] is not None
    assert keys.verify_api_key(key[:-1] + ("A" if key[-1] != "A" else "B")) is None
    assert keys.verify_api_key("") is None
    assert keys.verify_api_key("not-a-key") is None
    lm.client.delete("/api/keys/svc")
    assert keys.verify_api_key(key) is None


def test_plaintext_store_from_old_version_is_upgraded(lm, keys):
    old_key = "nk_" + "x" * 43
    keys.path.parent.mkdir(parents=True)
    keys.path.write_text(json.dumps({"legacy": {
        "key": old_key, "created": "2026-09-01T00:00:00Z", "last_used": None}}))

    listed = lm.client.get("/api/keys").json()
    assert listed["keys"][0]["prefix"] == old_key[:10] + "..."
    stored = json.loads(keys.path.read_text())["legacy"]
    assert "key" not in stored and stored["hash"] == keys._hash(old_key)
    assert keys.verify_api_key(old_key) == "legacy"


def test_corrupt_store_reads_as_empty(lm, keys):
    keys.path.parent.mkdir(parents=True)
    keys.path.write_text("{not json")
    assert lm.client.get("/api/keys").json() == {"keys": [], "count": 0}


# ── concurrent read-modify-write ─────────────────────────────────────────────

@pytest.mark.parametrize("other", ["generate", "delete"])
def test_overlapping_operations_do_not_lose_updates(lm, keys, monkeypatch, other):
    """A touch is paused between its load and its save; a second operation runs
    in that window. Without the store lock the touch then writes back its stale
    snapshot, losing a newly generated key or resurrecting a deleted one."""
    assert _generate(lm, "a").status_code == 200
    assert _generate(lm, "victim").status_code == 200

    real_save = keys._save_keys
    in_save, release = threading.Event(), threading.Event()
    paused = []

    def pausing_save(store):
        if threading.current_thread().name == "touch" and not paused:
            paused.append(True)
            in_save.set()
            assert release.wait(10), "test bug: touch was never released"
        real_save(store)

    monkeypatch.setattr(keys, "_save_keys", pausing_save)

    if other == "generate":
        op = lambda: asyncio.run(keys.generate_api_key("fresh"))
    else:
        op = lambda: asyncio.run(keys.delete_api_key("victim"))
    touch = threading.Thread(name="touch", target=lambda: asyncio.run(keys.touch_api_key("a")))
    second = threading.Thread(name="second", target=op)

    touch.start()
    assert in_save.wait(10)
    second.start()
    # Locked: the second operation waits here. Unlocked: it finishes (and writes)
    # while the touch still holds its stale snapshot.
    second.join(0.3)
    release.set()
    touch.join(10)
    second.join(10)
    assert not touch.is_alive() and not second.is_alive()

    stored = json.loads(keys.path.read_text())
    assert stored["a"]["last_used"] is not None
    if other == "generate":
        assert "fresh" in stored
    else:
        assert "victim" not in stored
