# TASK-121 / TASK-122 / TASK-123 — backup script, NVLink validation, backup→restore

**Issues:** #45 (TASK-121), #46 (TASK-122), #59 (TASK-123)
**Result: NOT RUN ON THE HOST — repo-side review plus sandboxed dry runs only.**
Review found the backup script would have exited 0 and printed "Backup Complete" on the
real stack while backing up **none** of the eight Docker volumes it names, and the NVLink
script's 100 GB/s threshold is unreachable on this hardware. Both are fixed in-repo; the
fixes are unverified against the real host and are not deployed.

> **Honesty statement.** The workstation was unreachable and this machine has no GPUs.
> Nothing here touched a real Docker daemon, database, MinIO, `mc` alias or GPU.
> Every "ran" below is the real script under bash against **shim** `docker` / `mc` /
> `nvidia-smi` / `torch` and **synthetic** fixtures. Shims encode my understanding of those
> tools; they are not the tools. Real-host validation is still owed (see "Not covered").

## Scripts under review

| Task | Script | Note |
| --- | --- | --- |
| #45 | `scripts/backup.sh` | exists; rewritten in part (below) |
| #46 | `/opt/scripts/validate-nvlink.py` | **no standalone file in the repo.** `configs/drivers/validate-nvlink.py` does not exist, so `scripts/deploy-phase02.sh` (Step 7, heredoc at ~L275-335) writes the embedded copy. That heredoc *is* the script, which is why `deploy-phase02.sh` changed. |
| #46 | `configs/drivers/verify-drivers.sh` | NVLink link/topology checks; **reviewed only, not edited** (outside the `scripts/` scope given) |
| #59 | `loadout-manager/api/backup.py` | **read-only review** |

There is no `scripts/restore.sh`. Restore is documented only as text inside the generated
`MANIFEST.txt`, plus the API endpoint.

## TASK-121 — `scripts/backup.sh`

### Defects found

| # | Defect (original `backup.sh`) | Severity |
| --- | --- | --- |
| 1 | **Volume names do not exist.** Every compose file sets a top-level `name:` (`ai-webui`, `ai-training`, `ai-monitoring`, `ai-storage`, …) and declares volumes without `name:`, so Docker creates `ai-webui_open-webui-data`, `ai-storage_qdrant-data`, etc. The script inspected the bare names, hit "Volume not found (skipping)", **returned 0**, and still printed "Backup Complete". | critical |
| 2 | **Three of the eight "volumes" are not volumes at all.** `n8n-data`, `authentik-postgres`, `langfuse-data` appear in no compose file. n8n is the bind mount `/data/n8n` (`compose.agentic.yml:13`); Authentik Postgres/redis/media are bind mounts under `/data/authentik` (`compose.auth.yml:15,31,62-63`); Langfuse lives in the shared `postgres` container's `postgres-data` volume (`compose.storage.yml`). n8n and Authentik are rated "Critical" in the runbook. | critical |
| 3 | Live file-level tar of a running PostgreSQL data directory is not a guaranteed-restorable backup; no `pg_dump`/`pg_dumpall` anywhere. | high |
| 4 | `set -e` plus `return 1` in `backup_volume`: the first real failure aborts the script — no remaining volumes, no manifest, no MinIO sync, no summary — and leaves the partial `.tar.gz` behind. | high |
| 5 | `./configs` is cwd-relative. Under cron (cwd=`$HOME`) it is silently skipped with no warning (systemd sets `WorkingDirectory`, which is why it can appear to work there). | high |
| 6 | Retention: `find "$BACKUP_ROOT" -maxdepth 1 -type d -mtime +30 -exec rm -rf` matches *any* directory (and `$BACKUP_ROOT` itself), not just run directories; it also runs when the current backup failed. Sandbox: with `BACKUP_ROOT` pointing at a dir holding two unrelated 2020-dated subdirs, the original deleted both. | high |
| 7 | Exit code hides failures: MinIO mirror failure, checkpoint/model tar failure and every `2>/dev/null` error path end in exit 0; `docker` missing or daemon down is not checked; a mistyped mode (`volume`) does nothing and reports success. | high |
| 8 | `MANIFEST.txt` is written *after* the MinIO sync, so it is never mirrored. | medium |
| 9 | Stderr from docker/tar is discarded, so the reason for any failure is invisible. | medium |
| 10 | No free-space check; no archive integrity check (a truncated gzip looks like a good backup). | medium |
| 11 | Backups written with the caller's umask; `configs/authentik/.env` (plaintext secrets, see `init-secrets.sh`) is swept into `project-configs.tar.gz` and mirrored to MinIO, contradicting `init-secrets.sh:230` ("keep it out of … backups"). | medium |
| 12 | Printed cron hint uses `$HOME/ai-workstation/…`, a path that does not exist (TASK-120 found the deployed copy under `/srv/src/src/beta-workstation`). | low |
| 13 | `find … \| tar -T -` without `--null` mishandles odd filenames; `/data/configs` (checked by the script) is created nowhere in the repo (`deploy-phase02.sh` creates `/data/config`). Not changed; skipped with a warning if absent. | low |

Findings 1–2 rest on the compose files in this repo. The live volume list was not
obtainable; if the host was ever started under the old `docker` project (see
`migrate-network.sh`) the real names may be `docker_<name>`. The fix resolves by suffix
rather than hardcoding a prefix for that reason.

### What changed

- `DATA_ROOT` (default `/data`) and `REPO_ROOT` (from `BASH_SOURCE`, same idiom as
  `deploy-*.sh`) replace hardcoded `/data` and `./configs`. `BACKUP_ROOT` default is unchanged in effect.
- `resolve_volume`: exact name, else a unique `<project>_<name>` match; ambiguous → failure.
- Volume list corrected to what the compose files create; `n8n` and `authentik` are taken from
  their bind-mount dirs by a root `alpine` container (the Postgres dir is not readable by the
  invoking user); `postgres-data` replaces `langfuse-data`.
- New `backup_postgres`: `pg_dumpall` via `docker exec` for `postgres` (user `admin`) and
  `authentik-postgres` (user `authentik`) → `*.sql.gz`, skipped with a warning if the
  container is not running. **This is new behaviour**, added because findings 3 and the
  issue's prerequisites call for it; it is the part I am least able to vouch for without a real
  container.
- Failures are accumulated, the run continues, the manifest lists `FAILED`/`Skipped`, and the
  exit code is 1 if anything failed or nothing was backed up.
- Prereqs: docker daemon reachable, valid mode, `BACKUP_MIN_FREE_GB` (default 20) → exit 2.
- Each archive is `gzip -t`-verified; failed/partial archives are removed.
- `umask 077`; `--exclude=.env` on the configs archive.
- Manifest written before the MinIO sync. `mc` configured but mirror failed → exit 1;
  `mc` not configured → warning only (as the issue allows).
- Retention restricted to `YYYYMMDD-HHMMSS` directories, `-mindepth 1`, and skipped on failure.

Exit codes: 0 ok, 1 backup/verification failure, 2 usage or prerequisite.

### Sandbox evidence

`bash -n` clean. `shellcheck 0.11` (via the `shellcheck-py` wheel): two SC2012 *info* notes
(`ls | awk`/`ls | wc`, both pre-existing style); nothing else. Scripts were run from an
unrelated cwd against fixture volumes named as the compose files would name them.

| Scenario | Original | New |
| --- | --- | --- |
| All 6 compose volumes + bind dirs + 2 PG containers present | all 8 volumes skipped; **exit 0, "Backup Complete"**; only MANIFEST.txt produced | 14 archives + MANIFEST, mirrored incl. MANIFEST; exit 0; `.env` absent from configs archive |
| qdrant tar fails | (name never matched) | other 13 archives kept, qdrant partial removed, manifest `## FAILED`, cleanup skipped, old run dir kept; **exit 1** |
| First volume tar fails (original names present) | aborts: 1 partial archive, no manifest/sync; exit 1 | n/a (continues) |
| Archive truncated but tar exits 0 | undetected | "failed integrity check", removed; exit 1 |
| `mc` alias absent | warning, exit 0 | warning, exit 0 |
| `mc mirror` fails | warning, exit 0 | **exit 1** |
| Docker daemon down | n/a | exit 2 |
| Unknown mode | exit 0 | exit 2 |
| Free-space below threshold | none | exit 2, empty run dir removed |
| Postgres container not running | n/a | skipped, exit 0 |
| `pg_dumpall` fails | n/a | exit 1 |
| Two volumes match `*_qdrant-data` | n/a | ambiguous → exit 1 |
| No volumes, no data dirs, `volumes` mode | n/a | "nothing backed up", exit 1 |
| Retention (old `2020…` run dir, old non-run dir, recent run dir) | removes any old dir | removes only the old run dir |
| `configs` mode, cwd ≠ repo | `./configs` skipped | resolved from script path |

## TASK-122 — NVLink validation

### Topology the script must match

From `docs/validation/TASK-014-nvlink-topology-display.md` (captured on the host): `NV4`
between GPU0↔GPU3 (Bridge A) and GPU1↔GPU2 (Bridge B), PHB/NODE elsewhere. The script's
`NVLINK_PAIRS` (0,3)(3,0)(1,2)(2,1) and `PCIE_PAIRS` (0,1)(1,0)(2,3)(3,2) match that.

### Defects in the embedded `validate-nvlink.py`

1. **Threshold is physically unreachable.** The repo's own spec (`plan/PROJECT_PLAN.md:51-52`,
   `plan/UI/Steps/00-master-spec.md:88-89`) gives each bridge 4 × 14.062 = **56.25 GB/s per
   direction**. The script measures a one-direction `copy_` and requires `> 100 GB/s`; the issue
   expects "~200+". On healthy hardware this reports `WARNING: CHECK NVLINK BRIDGES`. (112.5 GB/s
   is the bidirectional aggregate.)
2. **Wrong synchronization → false pass.** `torch.cuda.synchronize()` with no argument waits
   only on the current device (cuda:0), but the copy is queued on the source device. For pairs
   not involving GPU0 (1↔2, 2↔3, 3→2) nothing is waited on and the script reports an
   absurdly large "bandwidth". That includes the Bridge B pair, so a dead or degraded Bridge B
   could be reported ✓. (Model-based; see below.)
3. `gb=4` with `1024**3` measured GiB/s but printed GB/s.
4. No GPU-count check (traceback on fewer than 4 GPUs), no peer-access check, no handling of
   CUDA OOM when a loadout still holds the GPUs; every failure exited 1, indistinguishable from
   "bridge slow".

### What changed (in `scripts/deploy-phase02.sh`, heredoc and the final echo line only)

Per-device sync on both `a` and `b`; decimal GB; threshold `NVLINK_MIN_GBPS` default **35**
(above PCIe 4.0 x16 peer copies at ~25-31 GB/s, below healthy NVLink ~45-55); GPU-count and
`can_device_access_peer` checks; exit 0 healthy / 1 bridge below threshold / 2 cannot run.
The `35` is derived from the spec, **not measured** — the first real run should be recorded and
the number tuned. The closing echo line was updated so it no longer promises `> 100 GB/s`.
`plan/steps/02-host-baseline.md:291` and issue #46 still say `>100`; I did not touch plan docs.

### Sandbox evidence (synthetic `torch` model)

A small fake `torch` models async cross-device `copy_` on the source stream and per-device
`synchronize`. It is my model of PyTorch semantics, not PyTorch.

| Scenario | Old script | New script |
| --- | --- | --- |
| Healthy (NVLink pairs 50 GB/s, others 24) | Bridge A pairs 46.6 → ✗; Bridge B pairs `400000 GB/s` ✓; exit 1 | all ✓, exit 0 |
| Bridge B at half rate (25 GB/s) | Bridge B still ✓ (`400000 GB/s`); exit 1 only because of Bridge A | Bridge B ✗, exit 1 |
| No NVLink anywhere (24 GB/s) | not run | all four ✗, exit 1 |
| P2P unavailable GPU0→GPU3 | not run | that pair ✗, exit 1 |
| 2 GPUs visible | not run | message, exit 2 |
| OOM on allocation | not run | message, exit 2 |

### `verify-drivers.sh` (reviewed, not edited)

Run against a shim `nvidia-smi` whose `topo -m` body is the matrix captured in TASK-014 and
whose `nvlink --status` output follows my recollection of driver 5xx (`Link N: 14.062 GB/s` /
`Link N: <inactive>`):

- **Check [5] counts `grep -c "Active"`.** In that format the word never appears, so a fully
  healthy host reports `0/4 links active` and fails. If your driver does print "Active" this is
  moot — **confirm against the real `nvidia-smi nvlink -s` output.** Safer parse: count lines
  matching `Link [0-9]+:.*GB/s`.
- **Check [6] cannot fail.** The `topo -m` matrix has no `GPUa … NVx … GPUb` on one line, so the
  regex never matches, and the `|| grep -q "NV"` fallback matches the `NV#` legend that
  `topo -m` always prints. Run with a topology containing no NVLink at all, both pair checks
  still PASS. Safer: read row `GPUa`, column `GPUb` of the matrix and require `^NV[0-9]+$`.
- `TOPO_OUTPUT=$(nvidia-smi topo -m …)` under `set -e` exits silently if the command fails.

I left this file alone because it is outside `scripts/`; it needs a follow-up edit.

## TASK-123 — backup→restore via API (read-only review of `loadout-manager/api/backup.py`)

Cycle not executed. Code-reading findings:

1. **Endpoints differ from the issue.** Real routes: `POST /api/backup/run` (SSE),
   `GET /api/backup/history`, `POST /api/backup/restore/{id}`, `DELETE /api/backup/{id}`.
   `POST /api/backup` does not exist. (The restore code is real, not mocked — the issue is right.)
2. **History is an in-memory list seeded with three fabricated entries** (`backup.py:27-34`) whose
   archives will not exist: restoring `1`/`2` → 404 "Archive not found"; `3` → 400 (this is the
   issue's intended failure path, and it does 400 as written). New runs get id `len+1`
   (`:102`), which collides after any delete. History is lost on restart and the `on_disk` glob
   (`:56`) is computed but never used, so a pre-restart archive cannot be restored through the API.
3. **Container/host mismatch.** `docker/compose.loadout.yml` mounts only `/data/models/vllm`.
   `BACKUP_DIR` (`/data/backups`) and `RESTORE_TARGET` (`/data`) therefore resolve inside the
   container: a backup run would tar the container's `/data` (which is the vLLM weights mount) into
   the container's writable layer, and restore would extract there. Unless `BACKUP_DIR` /
   `RESTORE_TARGET` are overridden with mounts that are not in the compose file, a cycle cannot
   restore host state. (`BACKUP_DIR` / `RESTORE_TARGET` are not set in any compose file either.)
4. **Stop step is broken and unchecked.** `docker compose --project-directory /opt/loadout stop`
   (`:140-143`): `/opt/loadout` is not mounted in the image (compose files are at `/compose`),
   and `stop_proc.returncode` is never checked (`:151`), so extraction proceeds over live data
   regardless. If it did resolve, the loadout project contains only the manager itself, and no
   other stack (webui, storage, auth, …) would be stopped.
5. **Not safe on failure.** No `tar -tzf` pre-check, no pre-restore snapshot; a corrupt or
   truncated archive partially extracts and the endpoint reports "check data integrity".
   Services are not restarted. `--strip-components=1` is right for archives this endpoint made
   (members `data/…`) and wrong for anything else, including `scripts/backup.sh` output.
6. **Two incompatible backup formats.** The API archives `/data` only; Docker named volumes
   (open-webui, qdrant, postgres, …) live under `/var/lib/docker/volumes` and are not in it, and
   there are no SQL dumps. `scripts/backup.sh` produces a directory of per-source archives with no
   restore tool. Neither matches the other, so "no data loss … matches the state at backup time"
   cannot hold for volume-resident data via the API.
7. In the default `KOVATI_OS_MODE=workstation` the auth middleware (`main.py:42-62`) is a no-op,
   CORS is `*` with credentials, and the manager publishes `8800`: the destructive restore
   endpoint is unauthenticated on the LAN. (Appliance mode requires the Authentik header.)

I did not modify the API (read-only per instructions); these should become separate issues.

## Not covered

- Any execution against the real host: real volume names, real Docker/Compose behaviour,
  `pg_dumpall` against the real Postgres roles, `alpine` image availability, bind-mount
  ownership/permissions, `umask 077` (NTFS here does not enforce POSIX modes, so the directory
  showing 755 in the sandbox proves nothing either way), real disk-space figures, run time/size.
- MinIO: TASK-120 reports the `mc` alias `local` returns Access Denied on the host (credentials
  rotated in the repo but not deployed). Expect "MinIO client not configured (skipping sync)"
  there until that is fixed; the new script then exits 0 with that warning. MinIO-side
  retention does not exist and I did not add it.
- The deployed copy under `/srv/src/src/beta-workstation` is behind `main` (TASK-120); none of
  this reaches the host until it is updated.
- Real NVLink bandwidth: no GPUs here. The `35 GB/s` default and every number in the NVLink
  tables are model/spec values, not measurements. `nvidia-smi nvlink -s` / `topo -m` fixtures are
  synthetic (topo matrix body excepted).
- Not backed up by the script even after the fix: `/data/minio` (it is the sync target;
  including it would recurse), `dify-*`, `invokeai-db`, `comfyui-custom-nodes`,
  `alertmanager-data`, `caddy-config`, `/data/notebooks`, `/data/datasets`, `docker/.env`
  (deliberately; keep a separate copy — without it a restore cannot start the stack).
- No `restore.sh` was written; destructive and unverifiable here.
- `plan/steps/14-operations-runbook.md` still shows the old naive script and `~/ai-workstation`
  paths; not edited.

## Verdict

- **TASK-121:** not validated on the host. The script as committed would have silently backed up
  nothing from Docker volumes while exiting 0. Fixed in-repo and exercised in a sandbox; re-run
  on the host after deploying, with `docker volume ls` output attached, before closing #45.
- **TASK-122:** not run (no GPUs). Script defects fixed; threshold changed from the issue's
  100 GB/s to a spec-derived 35 GB/s, which needs a real baseline run. `verify-drivers.sh`
  needs a follow-up edit.
- **TASK-123:** not run. The restore path is not safe to exercise as written (findings 3–5);
  do not run it against a production host until fixed.
