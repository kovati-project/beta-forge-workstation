#!/usr/bin/env bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: this script needs bash - run: bash $0" >&2; exit 1; }
# deploy-integration-2026-11.sh — run docs/runbooks/deploy-integration-2026-11.md
# steps 1 and 4-9 on Adapress without touching vllm-4gpu / vllm-embed.
#
# Usage (as kasemo, NOT with sudo; it asks for sudo itself for steps 1 and 9):
#   cd /home/kasemo/share/src/beta-workstation
#   bash scripts/deploy-integration-2026-11.sh                # all steps
#   bash scripts/deploy-integration-2026-11.sh --from 6c      # resume at a step
#   bash scripts/deploy-integration-2026-11.sh --dry-run      # print, change nothing
#
# Steps: 1 backup, 4 preflight, 5 stray containers, 6a..6h stacks, 7 loadout UI,
#        8 verify, 9 backup timer.
#
# Guards: refuses to run outside the share path or as root; aborts if the
# preflight would recreate a vLLM container; re-checks after every step that
# vllm-4gpu and vllm-embed still have the same container ID and start time.

set -Eeuo pipefail

SHARE_REPO=/home/kasemo/share/src/beta-workstation
STEPS=(1 4 5 6a 6b 6c 6d 6e 6f 6g 6h 7 8 9)
FROM=1
DRY=false
LOG="$HOME/deploy-integration-$(date +%Y%m%d-%H%M%S).log"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from)    FROM=${2:?--from needs a step}; shift 2 ;;
    --dry-run) DRY=true; shift ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *)         echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
printf '%s\n' "${STEPS[@]}" | grep -qx "$FROM" || { echo "unknown step '$FROM' (one of: ${STEPS[*]})" >&2; exit 2; }

# ── Guards ────────────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] || { echo "run as kasemo, not root (npm and compose must not write root-owned files)" >&2; exit 1; }
cd "$SHARE_REPO"            # logical path: keeps the share path in compose's bind mounts
REPO=$PWD
[[ $REPO == "$SHARE_REPO" ]] || { echo "not in $SHARE_REPO" >&2; exit 1; }

exec > >(tee -a "$LOG") 2>&1
echo "log: $LOG   commit: $(git rev-parse --short HEAD) ($(git rev-parse --abbrev-ref HEAD))   from step: $FROM   dry-run: $DRY"

# ── Helpers ───────────────────────────────────────────────────────────────────
step() { echo; echo "════ step $1: $2 ════"; }
die()  { echo "✗ $*" >&2; echo "  resume with: bash scripts/deploy-integration-2026-11.sh --from $CUR" >&2; exit 1; }
run()  { echo "+ $*"; $DRY || "$@"; }
dcp()  { local proj=$1 file=$2; shift 2
         run docker compose -p "$proj" --project-directory "$REPO/docker" \
           --env-file "$REPO/docker/.env" -f "$REPO/docker/$file" "$@"; }
trap 'die "command failed (line $LINENO)"' ERR

vllm_state() { docker inspect vllm-4gpu vllm-embed --format '{{.Name}} {{.Id}} {{.State.StartedAt}} {{.State.Running}}'; }
VLLM_BEFORE=$(vllm_state) || { echo "vLLM containers not found" >&2; exit 1; }
check_vllm() {
  [[ "$(vllm_state)" == "$VLLM_BEFORE" ]] || { echo "vLLM state changed!"; echo "before: $VLLM_BEFORE"; echo "now:    $(vllm_state)"; die "STOP: vLLM was touched"; }
  echo "  ✓ vLLM untouched"
}

# wait_up PROJECT FILE SVC... : each service running, and healthy if it has a healthcheck
wait_up() {
  $DRY && return 0
  local proj=$1 file=$2; shift 2
  local svc id st
  for svc in "$@"; do
    for _ in $(seq 1 60); do
      id=$(docker compose -p "$proj" --project-directory "$REPO/docker" --env-file "$REPO/docker/.env" \
             -f "$REPO/docker/$file" ps -q "$svc" 2>/dev/null || true)
      st=$([[ -n $id ]] && docker inspect "$id" --format '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' || echo missing)
      case $st in running/healthy|running/none) break ;; esac
      sleep 5
    done
    case $st in
      running/healthy|running/none) echo "  ✓ $svc $st" ;;
      *) [[ -n $id ]] && docker logs "$id" --tail 50 || true; die "$svc not up ($st)" ;;
    esac
  done
}

up() { local proj=$1 file=$2; shift 2
       dcp "$proj" "$file" up -d --no-deps "$@"; wait_up "$proj" "$file" "$@"; check_vllm; }

reached=false
want() { [[ $1 == "$FROM" ]] && reached=true; $reached && CUR=$1; }

# ── Steps ─────────────────────────────────────────────────────────────────────
CUR=$FROM
docker ps --format '{{.Names}} {{.Status}}' | sort > "$HOME/pre-deploy-ps-$(date +%Y%m%d-%H%M%S).txt"

if want 1; then
  step 1 "backup (sudo, ~10-20 min)"
  run sudo bash scripts/backup.sh all
  $DRY || ls -lt /data/backups | sed -n 2p
fi

if want 4; then
  step 4 "preflight (read-only)"
  out=$(bash scripts/predeploy-check.sh) || true
  echo "$out"
  echo "$out" | grep -E '^(RECREATE|MISMATCH)' | grep -qE '\svllm-(4gpu|embed)\s' && die "preflight would recreate vLLM"
  extra=$(echo "$out" | awk '$1=="MISMATCH"{print $2}' | grep -vxE 'alertmanager|axolotl|invokeai' || true)
  [[ -z $extra ]] || die "unexpected MISMATCH: $extra"
  echo "  ✓ preflight as expected"
fi

if want 5; then
  step 5 "remove stray 'docker'-project containers"
  for c in alertmanager axolotl invokeai; do
    proj=$(docker inspect "$c" --format '{{index .Config.Labels "com.docker.compose.project"}}' 2>/dev/null || true)
    if [[ $proj == docker ]]; then run docker rm -f "$c"; else echo "  - $c: not in project 'docker' (${proj:-absent}), left alone"; fi
  done
  check_vllm
fi

if want 6a; then
  step 6a "storage"
  dcp ai-storage compose.storage.yml build minio
  up ai-storage compose.storage.yml postgres qdrant minio
  run bash scripts/setup-minio-buckets.sh
  run python3 scripts/setup-qdrant.py
fi
if want 6b; then step 6b "auth";       up ai-auth-stack compose.auth.yml postgres redis authentik authentik-worker; fi
if want 6c; then step 6c "monitoring"; up ai-monitoring compose.monitoring.yml prometheus grafana alertmanager node-exporter cadvisor dcgm-exporter; fi
if want 6d; then step 6d "voice";      up ai-voice compose.voice.yml whisper piper piper-openai; fi
if want 6e; then step 6e "web UI";     up ai-webui compose.webui.yml searxng open-webui; fi
if want 6f; then step 6f "agentic";    up ai-agentic compose.agentic.yml n8n dify-api dify-db dify-redis; fi
if want 6g; then
  step 6g "studio + training (not kohya)"
  up ai-studio   compose.studio.yml   comfyui rembg
  up ai-training compose.training.yml jupyterlab label-studio
fi
if want 6h; then step 6h "caddy";      up ai-caddy compose.caddy.yml caddy; fi

if want 7; then
  step 7 "loadout manager"
  run bash scripts/deploy-ui.sh
  check_vllm
  if ! $DRY; then
    status=$(curl -sf localhost:8800/status | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["active_profile"], sorted(d["running_services"]))')
    echo "  status: $status"
    [[ $status == "inference-4gpu ['vllm-4gpu', 'vllm-embed']" ]] || die "unexpected loadout status"
  fi
fi

if want 8; then
  step 8 "verify"
  if ! $DRY; then
    bash scripts/predeploy-check.sh || echo "  ! predeploy-check exit $? (RECREATE is OK only for langfuse and mcp-*)"
    m1=$(curl -sf localhost:8002/v1/models | grep -o '"id":"[^"]*"' | head -1); echo "  8002: $m1"
    m2=$(curl -sf localhost:8003/v1/models | grep -o '"id":"[^"]*"' | head -1); echo "  8003: $m2"
    [[ -n $m1 && -n $m2 ]] || die "a vLLM endpoint did not answer"
    check_vllm
    bash scripts/healthcheck.sh || echo "  ! healthcheck.sh reported problems (exit $?); see above"
  fi
fi

if want 9; then
  step 9 "nightly backup timer (sudo)"
  run sudo bash scripts/install-backup-timer.sh
  run sudo systemctl start ai-workstation-backup.service
  run sudo journalctl -u ai-workstation-backup -n 30 --no-pager
fi

$reached || die "step $FROM never reached"
echo; echo "✓ done. vLLM: $(vllm_state | awk '{print $1, $3}' | tr '\n' ' ')"; echo "log: $LOG"
