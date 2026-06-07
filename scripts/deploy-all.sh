#!/usr/bin/env bash
# Full-stack deployment orchestrator. Run on the workstation as kasemo.
#
# Usage:
#   bash scripts/deploy-all.sh                        # deploy phases 03–14
#   bash scripts/deploy-all.sh --from 08              # start from phase 08
#   bash scripts/deploy-all.sh --from 08 --to 10      # phases 08–10 only
#   bash scripts/deploy-all.sh --phase 13             # single phase
#   bash scripts/deploy-all.sh --validate             # run validate-phaseNN.sh after each deploy
#   bash scripts/deploy-all.sh --dry-run              # list phases that would run, no exec
#
# Phase 14 (systemd setup) calls sudo — run with a user that has sudo access.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Defaults ──────────────────────────────────────────────────────────────────
FROM_PHASE=3
TO_PHASE=14
SINGLE_PHASE=""
VALIDATE=false
DRY_RUN=false
FAILED_PHASES=()
SKIPPED_PHASES=()

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --from)       FROM_PHASE="$2"; shift 2 ;;
        --to)         TO_PHASE="$2";   shift 2 ;;
        --phase)      SINGLE_PHASE="$2"; FROM_PHASE="$2"; TO_PHASE="$2"; shift 2 ;;
        --validate)   VALIDATE=true;   shift ;;
        --dry-run)    DRY_RUN=true;    shift ;;
        --help|-h)
            sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Phase definitions ─────────────────────────────────────────────────────────
# Each entry: "phase_number|display_name|deploy_script|notes"
# deploy_script is relative to REPO_ROOT.
# notes are printed before running (pre-flight info).
declare -a PHASES=(
    "3|Text Inference (Ollama + vLLM)|scripts/deploy-phase03.sh|Requires /data/models/ollama to exist (setup-storage.sh). vLLM model download is separate."
    "4|Image Inference (ComfyUI + Real-ESRGAN)|scripts/deploy-phase04.sh|"
    "5|Open WebUI (UI + SearXNG)|scripts/deploy-phase05.sh|Requires Phase 03."
    "6|Loadout Manager (GPU orchestrator)|scripts/deploy-phase06.sh|"
    "7|Training Pipeline (Kohya + Axolotl + JupyterLab)|scripts/deploy-phase07.sh|"
    "8|Agentic Workflows & MCP (n8n + Dify)|scripts/deploy-phase08.sh|n8n owner account created manually after deploy."
    "9|Storage, Vector DB & RAG (MinIO + Qdrant + Postgres + Langfuse)|scripts/deploy-phase09.sh|Update secrets in compose.storage.yml before deploying."
    "10|Monitoring (Prometheus + Grafana + DCGM)|scripts/deploy-phase10.sh|Change GF_SECURITY_ADMIN_PASSWORD in compose.monitoring.yml first."
    "11|Code Generation (OpenHands + Continue.dev)|scripts/deploy-phase11.sh|Pull code models first: ollama pull qwen2.5-coder:32b"
    "12|Voice I/O (Whisper STT + Piper TTS)|scripts/deploy-phase12.sh|First start downloads whisper-large-v3 (~1.5GB). Allow 2-5 min."
    "13|Security Hardening (Authentik + UFW)|scripts/deploy-phase13.sh|Auto-generates .env secrets. Requires /data/authentik dirs."
    "14|Operations Runbook (systemd auto-start + backup)|scripts/setup-systemd-service.sh|Requires sudo. Installs systemd units and timers."
)

# ── Validate scripts ──────────────────────────────────────────────────────────
declare -A VALIDATE_SCRIPTS=(
    [3]="scripts/validate-phase03.sh"
    [4]="scripts/validate-phase04.sh"
    [5]="scripts/validate-phase05.sh"
    [6]="scripts/validate-phase06.sh"
    [7]="scripts/validate-phase07.sh"
    [8]="scripts/validate-phase08.sh"
    [9]="scripts/validate-phase09.sh"
    [10]="scripts/validate-phase10.sh"
    [11]="scripts/validate-phase11.sh"
    [12]="scripts/validate-phase12.sh"
    [13]="scripts/validate-phase13.sh"
)

# ── Helpers ───────────────────────────────────────────────────────────────────
log()      { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $*"; }
warn()     { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()      { echo -e "${RED}[ERROR]${NC} $*" >&2; }
phase_hdr(){ echo -e "\n${BLUE}━━━ Phase $1 — $2 ━━━${NC}"; }

# ── Pre-flight ────────────────────────────────────────────────────────────────
cd "$REPO_ROOT"

echo -e "${BLUE}=== AI Workstation Deployment ===${NC}"
echo "Repo root:    $REPO_ROOT"
echo "Phase range:  $FROM_PHASE – $TO_PHASE"
[[ "$VALIDATE" == true ]]  && echo "Validation:   enabled"
[[ "$DRY_RUN"  == true ]]  && echo -e "${YELLOW}Mode:         DRY RUN${NC}"
echo ""

if ! docker info &>/dev/null; then
    err "Docker is not running. Start Docker first."
    exit 1
fi

# ── Check secrets are initialised ────────────────────────────────────────────
if [[ ! -f "$REPO_ROOT/docker/.env" ]] && [[ "$DRY_RUN" == false ]]; then
    err "docker/.env not found — secrets not initialised."
    err "Run:  bash scripts/init-secrets.sh"
    exit 1
fi

# ── Check /data/ directories exist ───────────────────────────────────────────
if [[ ! -d /data/models/ollama ]] && [[ "$DRY_RUN" == false ]]; then
    err "/data/models/ollama not found. Run:  sudo bash scripts/setup-storage.sh"
    exit 1
fi

# ── Main loop ─────────────────────────────────────────────────────────────────
for entry in "${PHASES[@]}"; do
    IFS='|' read -r num name script notes <<< "$entry"

    # Range check
    (( num < FROM_PHASE || num > TO_PHASE )) && continue

    phase_hdr "$num" "$name"

    # Notes / pre-flight message
    if [[ -n "$notes" ]]; then
        warn "$notes"
        echo ""
    fi

    # Dry run — just list
    if [[ "$DRY_RUN" == true ]]; then
        echo "  Would run: bash $script"
        [[ "$VALIDATE" == true && -n "${VALIDATE_SCRIPTS[$num]:-}" ]] && \
            echo "  Would validate: bash ${VALIDATE_SCRIPTS[$num]}"
        continue
    fi

    # Script existence check
    if [[ ! -f "$REPO_ROOT/$script" ]]; then
        err "Script not found: $script — skipping phase $num"
        SKIPPED_PHASES+=("$num")
        continue
    fi

    # Phase 14 requires sudo for systemd unit installation
    SUDO_PREFIX=""
    if [[ "$num" -eq 14 ]]; then
        if ! sudo -n true 2>/dev/null; then
            warn "Phase 14 needs sudo. Enter password when prompted."
        fi
        SUDO_PREFIX="sudo"
    fi

    # Execute deploy script
    START=$(date +%s)
    if $SUDO_PREFIX bash "$REPO_ROOT/$script"; then
        ELAPSED=$(( $(date +%s) - START ))
        log "Phase $num complete (${ELAPSED}s)"

        # Run validation if requested and validate script exists
        if [[ "$VALIDATE" == true && -n "${VALIDATE_SCRIPTS[$num]:-}" ]]; then
            local_validate="$REPO_ROOT/${VALIDATE_SCRIPTS[$num]}"
            if [[ -f "$local_validate" ]]; then
                echo ""
                echo "  Running validation..."
                if bash "$local_validate"; then
                    log "Phase $num validation passed"
                else
                    warn "Phase $num validation reported issues — continuing"
                fi
            fi
        fi
    else
        EXIT_CODE=$?
        err "Phase $num FAILED (exit $EXIT_CODE)"
        FAILED_PHASES+=("$num ($name)")
        echo ""
        read -rp "Phase $num failed. Continue to next phase? [y/N] " CONTINUE
        [[ "${CONTINUE,,}" != "y" ]] && break
    fi
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}━━━ Deployment Summary ━━━${NC}"
echo ""

if [[ ${#FAILED_PHASES[@]} -eq 0 && ${#SKIPPED_PHASES[@]} -eq 0 ]]; then
    echo -e "${GREEN}✓ All phases completed successfully${NC}"
elif [[ ${#FAILED_PHASES[@]} -eq 0 ]]; then
    echo -e "${YELLOW}⚠ Completed with skipped phases${NC}"
    echo "  Skipped: ${SKIPPED_PHASES[*]}"
else
    echo -e "${RED}✗ Completed with failures${NC}"
    for f in "${FAILED_PHASES[@]}"; do
        echo "  Failed: Phase $f"
    done
    [[ ${#SKIPPED_PHASES[@]} -gt 0 ]] && echo "  Skipped: ${SKIPPED_PHASES[*]}"
fi

echo ""
echo "Service URLs (if all phases deployed):"
echo "  Open WebUI:     http://10.10.10.2:3000"
echo "  Grafana:        http://10.10.10.2:3001"
echo "  n8n:            http://10.10.10.2:5678"
echo "  Authentik:      http://10.10.10.2:9080/if/flow/initial-setup/"
echo "  Loadout Status: http://10.10.10.2:8800/status"
echo "  OpenHands:      http://10.10.10.2:3003"
echo ""
echo "Run full health check:"
echo "  bash scripts/healthcheck.sh"
echo ""

[[ ${#FAILED_PHASES[@]} -gt 0 ]] && exit 1
exit 0
