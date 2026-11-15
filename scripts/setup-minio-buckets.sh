#!/bin/bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: this script needs bash - run: bash $0" >&2; exit 1; }
# Create the MinIO buckets the platform expects, and the outputs lifecycle rule.
#
#   models    model weights and checkpoints
#   loras     LoRA adapters
#   datasets  training datasets
#   outputs   generation outputs (objects expire after 90 days)
#   backups   scripts/backup.sh mirrors each run to backups/<run>/
#
# Idempotent: existing buckets and an existing expiry rule are left alone, so
# it is safe to re-run (deploy-phase09.sh runs it on every deploy).
#
# Runs the MinIO client (mc) that ships inside the minio server image, via
# `docker exec`, so nothing has to be installed on the host and no separate mc
# image is needed (MinIO no longer publishes images to Docker Hub or quay.io).
# Credentials come from docker/.env (MINIO_ROOT_PASSWORD; user "admin" as in
# compose.storage.yml) and are passed as an environment variable, never on a
# command line.
#
# Usage: bash scripts/setup-minio-buckets.sh [--check]
#   --check   report what is missing and exit 1 if anything is; change nothing
#
# Overrides: MINIO_ROOT_USER (admin), MINIO_ROOT_PASSWORD (from docker/.env),
#            MINIO_CONTAINER (minio), OUTPUTS_EXPIRY_DAYS (90)
#
# Exit: 0 ok, 1 something missing (--check) or a step failed, 2 usage,
#       3 minio not running or the credentials are rejected

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUCKETS=(models loras datasets outputs backups)

CHECK_ONLY=0
case "${1:-}" in
    "") ;;
    --check) CHECK_ONLY=1 ;;
    -h|--help) sed -n '3,28p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown argument: $1 (usage: $0 [--check])" >&2; exit 2 ;;
esac

if [ -z "${MINIO_ROOT_PASSWORD:-}" ] && [ -f "$REPO_ROOT/docker/.env" ]; then
    MINIO_ROOT_PASSWORD="$(grep -E '^MINIO_ROOT_PASSWORD=' "$REPO_ROOT/docker/.env" | tail -n1 | cut -d= -f2-)"
fi
if [ -z "${MINIO_ROOT_PASSWORD:-}" ]; then
    echo "ERROR: MINIO_ROOT_PASSWORD is not set and not found in docker/.env" >&2
    echo "       Run scripts/init-secrets.sh first." >&2
    exit 1
fi

command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not found" >&2; exit 1; }

MINIO_CONTAINER="${MINIO_CONTAINER:-minio}"
if [ "$(docker inspect -f '{{.State.Running}}' "$MINIO_CONTAINER" 2>/dev/null)" != "true" ]; then
    echo "ERROR: container '$MINIO_CONTAINER' is not running (deploy-phase09.sh starts it)" >&2
    exit 3
fi

export MINIO_ROOT_USER="${MINIO_ROOT_USER:-admin}"
export MINIO_ROOT_PASSWORD
export OUTPUTS_EXPIRY_DAYS="${OUTPUTS_EXPIRY_DAYS:-90}"
export BUCKETS_LIST="${BUCKETS[*]}"
export CHECK_ONLY

# The body runs inside the minio container (POSIX sh).
read -r -d '' MC_SCRIPT <<'SH' || true
set -u
if ! err=$(mc alias set local http://localhost:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" 2>&1 >/dev/null); then
    echo "ERROR: cannot log in to MinIO: $err" >&2; exit 3
fi
rc=0
for b in $BUCKETS_LIST; do
    if mc ls "local/$b" >/dev/null 2>&1; then
        echo "  ok       bucket $b"
    elif [ "$CHECK_ONLY" = 1 ]; then
        echo "  MISSING  bucket $b"; rc=1
    elif mc mb --ignore-existing "local/$b" >/dev/null; then
        echo "  created  bucket $b"
    else
        echo "  FAILED   bucket $b" >&2; rc=1
    fi
done

# Lifecycle: an expiry rule of the right length on outputs? The minio image
# has no grep, so match the compact JSON with a shell pattern:
#   {"Expiration":{"Days":90},...
has_rule() {
    json=$(mc ilm rule ls --json local/outputs 2>/dev/null) || return 1
    case "$json" in
        *"\"Expiration\":{\"Days\":$OUTPUTS_EXPIRY_DAYS}"*) return 0 ;;
        *) return 1 ;;
    esac
}
if ! mc ls local/outputs >/dev/null 2>&1; then
    : # reported above
elif has_rule; then
    echo "  ok       outputs expiry $OUTPUTS_EXPIRY_DAYS days"
elif [ "$CHECK_ONLY" = 1 ]; then
    echo "  MISSING  outputs expiry $OUTPUTS_EXPIRY_DAYS days"; rc=1
elif mc ilm rule add --expire-days "$OUTPUTS_EXPIRY_DAYS" local/outputs >/dev/null; then
    echo "  created  outputs expiry $OUTPUTS_EXPIRY_DAYS days"
else
    echo "  FAILED   outputs expiry rule" >&2; rc=1
fi
exit $rc
SH

echo "MinIO buckets (container $MINIO_CONTAINER):"
set +e
docker exec \
    -e MINIO_ROOT_USER -e MINIO_ROOT_PASSWORD \
    -e OUTPUTS_EXPIRY_DAYS -e BUCKETS_LIST -e CHECK_ONLY \
    "$MINIO_CONTAINER" sh -c "$MC_SCRIPT"
rc=$?
set -e

case $rc in
    0) echo "MinIO buckets: OK" ;;
    1) if [ "$CHECK_ONLY" = 1 ]; then echo "MinIO buckets: missing items (run without --check to create them)"
       else echo "MinIO buckets: one or more steps FAILED" >&2; fi ;;
    3) echo "Check MINIO_ROOT_PASSWORD in docker/.env matches the running minio container." >&2 ;;
    *) echo "ERROR: mc exited with $rc" >&2 ;;
esac
exit $rc
