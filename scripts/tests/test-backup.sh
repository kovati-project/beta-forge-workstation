#!/usr/bin/env bash
# Test harness for scripts/backup.sh. Runs the real script against a stub
# `docker` / `mc` on PATH and a temporary DATA_ROOT / BACKUP_ROOT, so it needs
# no Docker daemon, no root and no /data. What it can NOT prove: that the real
# docker CLI, alpine image, pg_dumpall or mc behave the way the stubs do.
#
# Usage: bash scripts/tests/test-backup.sh      (exit 0 = all tests passed)

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$(cd "$HERE/.." && pwd)/backup.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PASSES=0
FAILS=0
pass() { PASSES=$((PASSES + 1)); echo "  ok   $1"; }
fail() { FAILS=$((FAILS + 1)); echo "  FAIL $1"; }
check() { # check <description> <command...>
    local desc=$1
    shift
    if "$@"; then pass "$desc"; else fail "$desc"; fi
}

# ── stubs ─────────────────────────────────────────────────────────────────────
STUB="$WORK/bin"
mkdir -p "$STUB"

# docker stub. Knobs (env):
#   STUB_DOCKER_DOWN=1        `docker info` fails like a stopped daemon
#   STUB_VOLUMES="a b"        names `docker volume ls -q` prints / inspect knows
#   STUB_FAIL_SOURCES="x y"   `docker run` for these sources writes half an
#                             archive, prints to stderr and exits 1
#   STUB_PG_RUNNING="c d"     containers `docker inspect` reports running
cat > "$STUB/docker" <<'EOF'
#!/usr/bin/env bash
in_list() { local x; for x in $2; do [ "$x" = "$1" ] && return 0; done; return 1; }
case "$1" in
  info)
    if [ -n "${STUB_DOCKER_DOWN:-}" ]; then
      echo "Cannot connect to the Docker daemon at unix:///var/run/docker.sock" >&2
      exit 1
    fi
    echo "Server Version: stub" ;;
  volume)
    case "$2" in
      inspect) in_list "$3" "${STUB_VOLUMES:-}" ;;
      ls) for v in ${STUB_VOLUMES:-}; do echo "$v"; done ;;
    esac ;;
  ps) ;;
  inspect)
    c=${!#}
    if in_list "$c" "${STUB_PG_RUNNING:-}"; then echo true; else
      echo "Error: No such object: $c" >&2; exit 1; fi ;;
  exec)
    echo "-- stub dump of $2" ;;
  run)
    shift
    src="" dst=""
    while [ $# -gt 0 ]; do
      case "$1" in
        -v) case "$2" in
              *:/source:ro) src=${2%:/source:ro} ;;
              *:/backup) dst=${2%:/backup} ;;
            esac
            shift 2 ;;
        --rm) shift ;;
        alpine) shift; break ;;
        *) shift ;;
      esac
    done
    # remaining: tar czf /backup/<name>.tar.gz -C /source .
    out="$dst/${3#/backup/}"
    if in_list "$src" "${STUB_FAIL_SOURCES:-}"; then
      printf 'partial' > "$out"
      echo "tar: /source/big.db: Read error at byte 0: Input/output error" >&2
      exit 1
    fi
    echo "stub archive of $src" | gzip > "$out" ;;
  *) echo "stub docker: unhandled: $*" >&2; exit 99 ;;
esac
EOF

# mc stub: never configured, so the MinIO step is a deterministic warning
cat > "$STUB/mc" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF

# du stub: STUB_DU_FAIL=1 makes it fail, forcing an unexpected set -e abort
REAL_DU="$(command -v du)"
cat > "$STUB/du" <<EOF
#!/usr/bin/env bash
if [ -n "\${STUB_DU_FAIL:-}" ]; then echo "du: stub failure" >&2; exit 1; fi
exec "$REAL_DU" "\$@"
EOF
chmod +x "$STUB"/*

# ── helpers ───────────────────────────────────────────────────────────────────
ALL_VOLUMES="ai-webui_open-webui-data ai-training_label-studio-data ai-storage_postgres-data ai-monitoring_prometheus-data ai-monitoring_grafana-data ai-storage_qdrant-data"
N=0

# new_env: fresh DATA_ROOT/BACKUP_ROOT for one test case
new_env() {
    N=$((N + 1))
    DATA="$WORK/case$N/data"
    ROOT="$WORK/case$N/backups"
    mkdir -p "$DATA/n8n" "$DATA/authentik" "$ROOT"
    echo "n8n" > "$DATA/n8n/database.sqlite"
}

# run_backup <args...>: runs backup.sh; sets RC and OUT, and RUN to the new run dir
run_backup() {
    OUT=$(PATH="$STUB:$PATH" DATA_ROOT="$DATA" BACKUP_ROOT="$ROOT" BACKUP_MIN_FREE_GB=0 \
          bash "$SCRIPT" "$@" 2>&1)
    RC=$?
    RUN=$(find "$ROOT" -mindepth 1 -maxdepth 1 -type d -newer "$WORK/stamp$N" 2>/dev/null | head -1)
}
stamp() { touch "$WORK/stamp$N"; sleep 1; }

# make_old <dir>: create a directory dated 2020
make_old() { mkdir -p "$1"; touch -d '2020-01-01 00:00:00' "$1"; }

manifest_failed() { # names listed under "## FAILED" in the manifest
    awk '/^## FAILED/{f=1; next} /^##/{f=0} f && NF' "$RUN/MANIFEST.txt"
}

# ── tests ─────────────────────────────────────────────────────────────────────
echo "backup.sh: unknown mode"
new_env
run_backup volume
check "exits 2" [ "$RC" -eq 2 ]
check "prints usage" grep -q "Usage:" <<<"$OUT"
check "names the bad mode" grep -q "Unknown mode: 'volume'" <<<"$OUT"
check "creates no run directory" [ -z "$(ls -A "$ROOT")" ]

echo "backup.sh: --help"
new_env
run_backup --help
check "exits 0" [ "$RC" -eq 0 ]
check "prints usage" grep -q "Usage:" <<<"$OUT"

echo "backup.sh: extra argument"
new_env
run_backup volumes extra
check "exits 2" [ "$RC" -eq 2 ]

echo "backup.sh: docker daemon down"
new_env
STUB_DOCKER_DOWN=1 run_backup volumes
check "exits 2" [ "$RC" -eq 2 ]
check "says the daemon is unreachable" grep -q "daemon is not reachable" <<<"$OUT"
check "shows docker's own error" grep -q "Cannot connect to the Docker daemon" <<<"$OUT"
check "creates no run directory" [ -z "$(ls -A "$ROOT")" ]

echo "backup.sh: all volumes succeed"
new_env
make_old "$ROOT/20200101-000000"
stamp
STUB_VOLUMES="$ALL_VOLUMES" STUB_PG_RUNNING="postgres authentik-postgres" run_backup volumes
check "exits 0" [ "$RC" -eq 0 ]
check "says Backup Complete" grep -q "Backup Complete" <<<"$OUT"
check "has a manifest without FAILED" bash -c '[ -f "$1" ] && ! grep -q "## FAILED" "$1"' _ "$RUN/MANIFEST.txt"
check "archived all 10 sources" [ "$(find "$RUN" -name '*.gz' | wc -l)" -eq 10 ]
check "manifest does not list itself" bash -c '! grep -q "  MANIFEST.txt" "$1"' _ "$RUN/MANIFEST.txt"

echo "backup.sh: one volume fails in the middle"
new_env
make_old "$ROOT/20200101-000000"
stamp
STUB_VOLUMES="$ALL_VOLUMES" STUB_PG_RUNNING="postgres authentik-postgres" \
STUB_FAIL_SOURCES="ai-storage_postgres-data" run_backup volumes
check "exits 1" [ "$RC" -eq 1 ]
check "says Backup FAILED" grep -q "Backup FAILED" <<<"$OUT"
check "writes a manifest" [ -f "$RUN/MANIFEST.txt" ]
check "manifest FAILED lists only postgres" [ "$(manifest_failed)" = "postgres" ]
check "removes the partial archive" [ ! -e "$RUN/postgres.tar.gz" ]
check "keeps going: volumes after it are archived" [ -f "$RUN/qdrant.tar.gz" ]
check "keeps going: dumps after it are archived" [ -f "$RUN/authentik-db-dump.sql.gz" ]
check "surfaces the tar error in the log" grep -q "Input/output error" <<<"$OUT"
check "skips retention" grep -q "Skipping cleanup" <<<"$OUT"
check "old run directory is kept" [ -d "$ROOT/20200101-000000" ]

echo "backup.sh: retention after a successful run"
new_env
make_old "$ROOT/20200101-000000"          # old run dir: removed
make_old "$ROOT/20200102-000000"          # old run dir: removed
make_old "$ROOT/keep-me"                  # old, not a run dir
make_old "$ROOT/20200103-000000.bak"      # old, run-like but not the pattern
make_old "$ROOT/2020-01-04"               # old, other date format
mkdir -p "$ROOT/20991231-000000"          # recent run dir (mtime now)
touch -d '2020-01-01' "$ROOT/old-file-20200101-000000"
stamp
STUB_VOLUMES="$ALL_VOLUMES" run_backup volumes
check "exits 0" [ "$RC" -eq 0 ]
check "removes old run directories" [ ! -e "$ROOT/20200101-000000" ]
check "removes every old run directory" [ ! -e "$ROOT/20200102-000000" ]
check "keeps old non-run directory" [ -d "$ROOT/keep-me" ]
check "keeps old run-like .bak directory" [ -d "$ROOT/20200103-000000.bak" ]
check "keeps old directory in another date format" [ -d "$ROOT/2020-01-04" ]
check "keeps old plain file" [ -f "$ROOT/old-file-20200101-000000" ]
check "keeps recent run directory" [ -d "$ROOT/20991231-000000" ]
check "keeps BACKUP_ROOT" [ -d "$ROOT" ]
check "keeps this run" [ -f "$RUN/MANIFEST.txt" ]
check "reports 2 removed" grep -q "Removed 2 of 2 old backup" <<<"$OUT"

echo "backup.sh: retention skipped when nothing was backed up"
new_env
rm -rf "$DATA/n8n" "$DATA/authentik"
make_old "$ROOT/20200101-000000"
stamp
STUB_VOLUMES="" run_backup volumes
check "exits 1" [ "$RC" -eq 1 ]
check "manifest FAILED says nothing-backed-up" [ "$(manifest_failed)" = "nothing-backed-up" ]
check "old run directory is kept" [ -d "$ROOT/20200101-000000" ]

echo "backup.sh: unexpected abort mid-run (set -e)"
new_env
make_old "$ROOT/20200101-000000"
stamp
STUB_VOLUMES="$ALL_VOLUMES" STUB_DU_FAIL=1 run_backup volumes
check "exits non-zero" [ "$RC" -ne 0 ]
check "says it aborted" grep -q "aborted" <<<"$OUT"
check "still writes a manifest" [ -f "$RUN/MANIFEST.txt" ]
check "manifest FAILED says aborted" grep -qx "aborted" <(manifest_failed)
check "old run directory is kept" [ -d "$ROOT/20200101-000000" ]

echo "backup.sh: configs mode works without docker"
new_env
mkdir -p "$DATA/configs"
echo "lr: 1e-4" > "$DATA/configs/train.yaml"
stamp
STUB_DOCKER_DOWN=1 run_backup configs
check "exits 0" [ "$RC" -eq 0 ]
check "archives training configs" [ -f "$RUN/training-configs.tar.gz" ]
check "excludes .env from project configs" \
    bash -c '! tar tzf "$1" | grep -q "/\.env$"' _ "$RUN/project-configs.tar.gz"

echo ""
echo "backup.sh tests: $PASSES passed, $FAILS failed"
[ "$FAILS" -eq 0 ]
