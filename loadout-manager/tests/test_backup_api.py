"""
/api/backup/* — what the backup and restore endpoints actually do.

tar and docker are faked (``api.exec``) except in the round-trip test, which runs
real GNU tar on a temp tree. Nothing here touches /data or a Docker daemon.

Defects are xfail(strict=True) so a fix fails the run until the marker goes.
"""

import shutil
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]


def _seed(api, archive=True, status="success"):
    path = api.backups / "backup-20261001-0600.tar.gz"
    if archive:
        path.write_bytes(b"not really gzip")
    entry = {"id": "1", "date": "2026-10-01 06:00", "size": "0.0 GB", "status": status,
             "archive": str(path) if status == "success" else None}
    api.backup.BACKUP_HISTORY.append(entry)
    return entry


def _is_tar(verb):
    return lambda argv: argv[0] == "tar" and f"--{verb}" in argv


def _sse(resp):
    return [l[len("data: "):] for l in resp.text.splitlines() if l.startswith("data: ")]


# ── behaviour that is correct today ─────────────────────────────────────────

def test_run_archives_restore_target_into_backup_dir(api):
    r = api.client.post("/api/backup/run")
    assert r.status_code == 200
    (tar,) = [c for c in api.exec.calls if c[0] == "tar"]
    assert "--create" in tar and tar[-1] == str(api.data)
    target = next(a for a in tar if a.startswith("--file=")).split("=", 1)[1]
    assert Path(target).parent == api.backups and Path(target).name.startswith("backup-")
    assert api.backup.BACKUP_HISTORY[0]["archive"] == target
    assert api.backup.BACKUP_CONFIG["last_backup"]["status"] == "success"


def test_failed_tar_is_reported_and_not_recorded(api):
    api.exec.on(_is_tar("create"), rc=2, lines=["tar: /data/x: Cannot stat"])
    r = api.client.post("/api/backup/run")
    assert any("Backup failed (exit 2)" in l for l in _sse(r))
    assert api.backup.BACKUP_HISTORY == []
    assert api.backup.BACKUP_CONFIG["last_backup"] is None


def test_restore_unknown_backup_is_404_and_runs_nothing(api):
    assert api.client.post("/api/backup/restore/nope").status_code == 404
    assert api.exec.calls == []


def test_restore_of_a_failed_backup_is_refused(api):
    _seed(api, archive=False, status="fail")
    assert api.client.post("/api/backup/restore/1").status_code == 400
    assert api.exec.calls == []


def test_restore_with_archive_missing_on_disk_is_404(api):
    _seed(api, archive=False)
    assert api.client.post("/api/backup/restore/1").status_code == 404
    assert api.exec.calls == []


def test_restore_stops_services_before_extracting(api):
    _seed(api)
    api.client.post("/api/backup/restore/1")
    verbs = ["stop" if "stop" in c else "extract" if "--extract" in c else c[0]
             for c in api.exec.calls]
    assert verbs == ["stop", "extract"]


def test_delete_removes_entry_and_archive(api):
    entry = _seed(api)
    assert api.client.delete("/api/backup/1").status_code == 200
    assert not Path(entry["archive"]).exists()
    assert api.backup.BACKUP_HISTORY == []


# ── defects ─────────────────────────────────────────────────────────────────

@pytest.mark.xfail(
    strict=True,
    reason="BKP-1: BACKUP_HISTORY ships with three hard-coded June 2026 entries "
           "(42 GB, 41 GB, a failure) that never happened; a fresh install shows them "
           "as real history.")
def test_history_is_empty_when_no_backup_ever_ran(api):
    assert api.shipped_history == []


@pytest.mark.xfail(
    strict=True,
    reason="BKP-2: history lives only in memory; archives on disk are globbed into "
           "an unused variable and never listed, so every restart loses all history "
           "and makes every real archive unrestorable from the UI.")
def test_history_lists_archives_present_on_disk(api):
    (api.backups / "backup-20261002-0600.tar.gz").write_bytes(b"x")
    backups = api.client.get("/api/backup/history").json()["backups"]
    assert any(b["archive"].endswith("backup-20261002-0600.tar.gz") for b in backups)


@pytest.mark.xfail(
    strict=True,
    reason="BKP-3: the tar excludes a hard-coded '/data/backups', not BACKUP_DIR. "
           "With any other BACKUP_DIR under RESTORE_TARGET each backup contains every "
           "previous backup (and the archive being written).")
def test_backup_excludes_the_configured_backup_dir(api):
    api.client.post("/api/backup/run")
    (tar,) = [c for c in api.exec.calls if c[0] == "tar"]
    assert f"--exclude={api.backups}" in tar


@pytest.mark.xfail(
    strict=True,
    reason="BKP-4: a failed tar leaves its partial archive in BACKUP_DIR, where it "
           "looks like a real backup-*.tar.gz.")
def test_failed_backup_removes_partial_archive(api):
    def write_partial(argv):
        target = next(a for a in argv if a.startswith("--file=")).split("=", 1)[1]
        Path(target).write_bytes(b"truncated")
    api.exec.on(_is_tar("create"), rc=2, effect=write_partial)
    api.client.post("/api/backup/run")
    assert list(api.backups.glob("backup-*.tar.gz")) == []


@pytest.mark.xfail(
    strict=True,
    reason="BKP-5: restore ignores the return code of `docker compose stop` and "
           "extracts over the live data of services that are still running.")
def test_restore_aborts_if_services_did_not_stop(api):
    _seed(api)
    api.exec.on(lambda a: "stop" in a, rc=1, lines=["no configuration file provided"])
    api.client.post("/api/backup/restore/1")
    assert api.exec.find("--extract") == []


@pytest.mark.xfail(
    strict=True,
    reason="BKP-6: restore stops `--project-directory /opt/loadout`, a path that "
           "exists nowhere in this repo or the loadout-manager container (compose "
           "files are at /compose), so the stop step stops nothing.")
def test_restore_stops_the_real_compose_project(api):
    _seed(api)
    api.client.post("/api/backup/restore/1")
    (stop,) = api.exec.find("stop")
    assert "/opt/loadout" not in stop


@pytest.mark.xfail(
    strict=True,
    reason="BKP-7: DELETE of an unknown id reports success instead of 404.")
def test_delete_unknown_backup_is_404(api):
    assert api.client.delete("/api/backup/nope").status_code == 404


@pytest.mark.skipif(sys.platform == "win32" or shutil.which("tar") is None,
                    reason="needs GNU tar (runs in CI on Linux)")
@pytest.mark.xfail(
    strict=True,
    reason="BKP-8: backup stores RESTORE_TARGET by its absolute path, restore "
           "extracts with --strip-components=1. That only round-trips when "
           "RESTORE_TARGET is exactly one level deep (/data); anything deeper is "
           "restored into a nested copy and the originals are not restored.")
def test_backup_then_restore_round_trips(api):
    api.exec.passthrough(lambda a: a[0] == "tar")
    victim = api.data / "n8n" / "workflow.json"
    victim.parent.mkdir()
    victim.write_text('{"v": 1}')

    api.client.post("/api/backup/run")
    assert api.backup.BACKUP_HISTORY, "backup did not complete"
    victim.write_text('{"v": "corrupted"}')

    api.client.post(f"/api/backup/restore/{api.backup.BACKUP_HISTORY[0]['id']}")
    assert victim.read_text() == '{"v": 1}'


@pytest.mark.xfail(
    strict=True,
    reason="BKP-9: in the deployed container BACKUP_DIR (/data/backups) and "
           "RESTORE_TARGET (/data) are not mounted (only /data/models/vllm and "
           "/data/loadout-manager are), so backups are written to the container's "
           "ephemeral layer and contain almost nothing.")
def test_deployed_container_mounts_backup_dir_and_restore_target():
    svc = yaml.safe_load((REPO / "docker" / "compose.loadout.yml").read_text())
    vols = svc["services"]["loadout-manager"]["volumes"]
    targets = {v.split(":")[1] for v in vols}
    assert "/data" in targets
