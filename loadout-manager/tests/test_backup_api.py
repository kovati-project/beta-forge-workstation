"""
/api/backup/* — runs scripts/backup.sh in a helper container and reports the
runs it leaves under BACKUP_ROOT/<YYYYmmdd-HHMMSS>/.

docker is faked (``api.exec``); runs on disk are built by ``_make_run`` the way
backup.sh lays them out. What this can NOT prove: that backup.sh succeeds on
the host, or that the helper's mounts match the host's paths.
"""

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]


def _make_run(api, run_id, files=("open-webui.tar.gz", "postgres-dump.sql.gz"),
              failed=None, manifest=True):
    run = api.backups / run_id
    run.mkdir()
    for name in files:
        (run / name).write_bytes(b"x" * 1024)
    if manifest:
        text = "# Backup Manifest\nMode: all\n\n## Files\n"
        if failed:
            text += "\n## FAILED\n" + "\n".join(failed) + "\n"
        text += "\n## Restore Instructions\n# ...\n"
        (run / "MANIFEST.txt").write_text(text)
    return run


def _sse(resp):
    return [l[len("data: "):] for l in resp.text.splitlines() if l.startswith("data: ")]


def _helper(api):
    (cmd,) = [c for c in api.exec.calls if c[:2] == ["docker", "run"] and "backup.sh" in c[-2]]
    return cmd


# ── history and config come from disk ───────────────────────────────────────

def test_history_is_empty_when_no_backup_ever_ran(api):
    assert api.client.get("/api/backup/history").json() == {"backups": []}
    assert api.client.get("/api/backup/config").json()["last_backup"] is None


def test_history_lists_runs_on_disk_newest_first(api):
    _make_run(api, "20261001-020000")
    _make_run(api, "20261002-020000", failed=["qdrant"])
    _make_run(api, "20261003-020000", manifest=False)
    (api.backups / "not-a-run").mkdir()          # ignored: not a timestamped run
    (api.backups / "stray.tar.gz").write_bytes(b"x")

    backups = api.client.get("/api/backup/history").json()["backups"]
    assert [b["id"] for b in backups] == ["20261003-020000", "20261002-020000", "20261001-020000"]
    by_id = {b["id"]: b for b in backups}
    assert by_id["20261001-020000"]["status"] == "success"
    assert by_id["20261002-020000"]["status"] == "fail"
    assert by_id["20261002-020000"]["failed"] == ["qdrant"]
    assert by_id["20261003-020000"]["status"] == "incomplete"
    assert by_id["20261001-020000"]["files"] == 2
    assert by_id["20261001-020000"]["date"] == "2026-10-01 02:00"
    assert all(b["restorable"] is False for b in backups)


def test_history_honours_n(api):
    for day in range(1, 6):
        _make_run(api, f"202610{day:02d}-020000")
    assert len(api.client.get("/api/backup/history", params={"n": 2}).json()["backups"]) == 2


def test_config_reports_the_real_schedule_and_last_run(api):
    _make_run(api, "20261002-020000")
    cfg = api.client.get("/api/backup/config").json()
    assert cfg["schedule_editable"] is False and "systemd" in cfg["schedule_source"]
    assert cfg["destination"] == str(api.backups)
    assert cfg["last_backup"]["status"] == "success"


def test_schedule_cannot_be_changed_from_the_api(api):
    r = api.client.patch("/api/backup/config", params={"schedule": "0 3 * * *"})
    assert r.status_code == 501 and "systemctl" in r.json()["detail"]


# ── running a backup ────────────────────────────────────────────────────────

def test_run_executes_backup_sh_in_a_helper_with_host_paths(api):
    r = api.client.post("/api/backup/run")
    assert r.status_code == 200
    cmd = _helper(api)
    repo = "/srv/beta-workstation"
    assert cmd[-2:] == [f"{repo}/scripts/backup.sh", "all"]
    assert f"{repo}:{repo}:ro" in cmd                  # repo at its host path
    assert "/data:/data" in cmd                        # data at its host path
    assert "/var/run/docker.sock:/var/run/docker.sock" in cmd
    assert f"BACKUP_ROOT={api.backups.as_posix()}" in cmd
    assert cmd[cmd.index("--name") + 1] == "loadout-backup"
    assert _sse(r)[-1] == "✓ Backup complete"


def test_run_streams_script_output_without_colour_codes(api):
    api.exec.on(lambda a: "backup.sh" in " ".join(a),
                lines=["\x1b[0;32m[02:00:01]\x1b[0m Backing up: open-webui..."])
    lines = _sse(api.client.post("/api/backup/run"))
    assert "[02:00:01] Backing up: open-webui..." in lines


def test_failed_run_is_reported(api):
    api.exec.on(lambda a: "backup.sh" in " ".join(a), rc=1, lines=["=== Backup FAILED ==="])
    lines = _sse(api.client.post("/api/backup/run"))
    assert lines[-1].startswith("✗ Backup failed (exit 1)")


def test_run_without_host_compose_dir_is_503(api, monkeypatch):
    monkeypatch.setattr(api.backup, "HOST_COMPOSE_DIR", "")
    assert api.client.post("/api/backup/run").status_code == 503
    assert api.exec.calls == []


@pytest.mark.anyio
async def test_second_run_while_one_is_running_is_refused(api):
    await api.backup._run_lock.acquire()
    try:
        assert api.client.post("/api/backup/run").status_code == 409
    finally:
        api.backup._run_lock.release()
    assert api.exec.calls == []


def test_lock_is_released_after_a_run(api):
    api.client.post("/api/backup/run")
    assert not api.backup._run_lock.locked()
    assert api.client.post("/api/backup/run").status_code == 200


# ── restore and delete ──────────────────────────────────────────────────────

def test_restore_is_not_offered(api):
    _make_run(api, "20261001-020000")
    r = api.client.post("/api/backup/restore/20261001-020000")
    assert r.status_code == 501 and "MANIFEST.txt" in r.json()["detail"]
    assert api.exec.calls == []


def test_delete_removes_the_run_via_a_root_helper(api):
    _make_run(api, "20261001-020000")
    assert api.client.delete("/api/backup/20261001-020000").status_code == 200
    (cmd,) = api.exec.calls
    root = api.backups.as_posix()
    assert cmd[-3:] == ["rm", "-rf", f"{root}/20261001-020000"]


@pytest.mark.parametrize("bad", ["..", "20261001", "20261001-020000;rm", "x"])
def test_delete_rejects_anything_but_a_run_id(api, bad):
    assert api.client.delete(f"/api/backup/{bad}").status_code in (400, 404, 405)
    assert api.exec.calls == []


def test_delete_unknown_run_is_404(api):
    assert api.client.delete("/api/backup/20261001-020000").status_code == 404
    assert api.exec.calls == []


def test_failed_delete_is_reported(api):
    _make_run(api, "20261001-020000")
    api.exec.on(lambda a: "rm" in a, rc=1, lines=["rm: can't remove: Read-only file system"])
    r = api.client.delete("/api/backup/20261001-020000")
    assert r.status_code == 500 and "Read-only" in r.json()["detail"]


# ── deployment ──────────────────────────────────────────────────────────────

def test_deployed_container_can_read_the_backup_root():
    svc = yaml.safe_load((REPO / "docker" / "compose.loadout.yml").read_text(encoding="utf-8"))
    vols = svc["services"]["loadout-manager"]["volumes"]
    mounts = {(v["source"], v["target"]) if isinstance(v, dict) else tuple(v.split(":")[:2])
              for v in vols}
    assert ("/data/backups", "/data/backups") in mounts
