#!/usr/bin/env bash
# deploy-ui.sh — Build the React UI and redeploy the loadout-manager container.
#
# Usage:
#   ./scripts/deploy-ui.sh              # full build + docker rebuild + restart
#   ./scripts/deploy-ui.sh --build-only # build UI only, skip docker
#   ./scripts/deploy-ui.sh --docker-only # skip UI build, just rebuild + restart
#
# Requirements: node >= 18, npm, docker, docker compose v2

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_DIR="$REPO_ROOT/ui"
LM_DIR="$REPO_ROOT/loadout-manager"
STATIC_DIR="$LM_DIR/static"
COMPOSE_FILE="$REPO_ROOT/docker/compose.loadout.yml"
SERVICE_NAME="loadout-manager"
PORT=8800

# ── Argument parsing ──────────────────────────────────────────────────────────
BUILD_UI=true
BUILD_DOCKER=true

for arg in "$@"; do
  case "$arg" in
    --build-only)  BUILD_DOCKER=false ;;
    --docker-only) BUILD_UI=false ;;
    --help|-h)
      echo "Usage: $0 [--build-only | --docker-only]"
      echo "  --build-only   Build React UI only (no docker rebuild)"
      echo "  --docker-only  Skip UI build, just rebuild + restart container"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg  (use --help for usage)"
      exit 1
      ;;
  esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────
step() { echo ""; echo "── $* ──────────────────────────────────────────"; }
ok()   { echo "  ✓ $*"; }
fail() { echo "  ✗ $*" >&2; exit 1; }

echo "╔══════════════════════════════════════════════════╗"
echo "║           Kovati  —  UI Deploy Script            ║"
echo "╚══════════════════════════════════════════════════╝"
echo "  Repo:     $REPO_ROOT"
echo "  UI:       $UI_DIR"
echo "  Output:   $STATIC_DIR"
echo "  Compose:  $COMPOSE_FILE"
echo ""

# ── Step 1: Pre-flight checks ─────────────────────────────────────────────────
step "Pre-flight checks"

if $BUILD_UI; then
  command -v node >/dev/null 2>&1 || fail "node not found — install Node.js >= 18"
  command -v npm  >/dev/null 2>&1 || fail "npm not found"
  NODE_VER=$(node --version | sed 's/v//' | cut -d. -f1)
  [[ $NODE_VER -ge 18 ]] || fail "Node.js >= 18 required (found v$NODE_VER)"
  ok "node $(node --version), npm $(npm --version)"

  [[ -f "$UI_DIR/package.json" ]] || fail "package.json not found at $UI_DIR"
  ok "UI source found"
fi

if $BUILD_DOCKER; then
  command -v docker >/dev/null 2>&1 || fail "docker not found"
  docker compose version >/dev/null 2>&1 || fail "docker compose v2 not found"
  [[ -f "$COMPOSE_FILE" ]] || fail "Compose file not found: $COMPOSE_FILE"
  ok "docker $(docker --version | awk '{print $3}' | tr -d ',')"
fi

[[ -f "$LM_DIR/Dockerfile" ]]     || fail "Dockerfile not found at $LM_DIR"
[[ -f "$LM_DIR/main.py" ]]        || fail "main.py not found at $LM_DIR"
[[ -f "$LM_DIR/profiles.yaml" ]]  || fail "profiles.yaml not found at $LM_DIR"
ok "loadout-manager source found"

# ── Step 2: Install npm dependencies ─────────────────────────────────────────
if $BUILD_UI; then
  step "Installing npm dependencies"
  cd "$UI_DIR"

  if [[ -f "package-lock.json" ]]; then
    npm ci --silent
    ok "npm ci complete"
  else
    npm install --silent
    ok "npm install complete"
  fi
fi

# ── Step 3: Build React UI ────────────────────────────────────────────────────
if $BUILD_UI; then
  step "Building React UI"
  cd "$UI_DIR"

  # Vite outputs to ../loadout-manager/static (configured in vite.config.js)
  npm run build

  # Verify output
  [[ -d "$STATIC_DIR" ]]          || fail "Build output missing: $STATIC_DIR"
  [[ -f "$STATIC_DIR/index.html" ]] || fail "index.html missing from build output"

  ASSET_COUNT=$(find "$STATIC_DIR" -type f | wc -l)
  BUILD_SIZE=$(du -sh "$STATIC_DIR" | cut -f1)
  ok "Build complete — $ASSET_COUNT files, $BUILD_SIZE total → $STATIC_DIR"
fi

# ── Step 4: Rebuild Docker image ──────────────────────────────────────────────
if $BUILD_DOCKER; then
  step "Building Docker image"
  cd "$REPO_ROOT"

  docker compose -f "$COMPOSE_FILE" build \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    "$SERVICE_NAME"

  ok "Image built: loadout-manager:latest"
fi

# ── Step 5: Restart container ─────────────────────────────────────────────────
if $BUILD_DOCKER; then
  step "Restarting container"
  cd "$REPO_ROOT"

  # Bring down existing container (graceful)
  if docker compose -f "$COMPOSE_FILE" ps --quiet "$SERVICE_NAME" 2>/dev/null | grep -q .; then
    docker compose -f "$COMPOSE_FILE" stop "$SERVICE_NAME"
    ok "Stopped existing container"
  fi

  docker compose -f "$COMPOSE_FILE" up -d "$SERVICE_NAME"
  ok "Container started"

  # ── Step 6: Health check ─────────────────────────────────────────────────
  step "Waiting for health check"
  ATTEMPTS=0
  MAX=20
  until curl -sf "http://localhost:$PORT/health" >/dev/null 2>&1; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [[ $ATTEMPTS -ge $MAX ]]; then
      echo ""
      echo "  ✗ Health check failed after ${MAX} attempts"
      echo "  Logs:"
      docker compose -f "$COMPOSE_FILE" logs --tail=30 "$SERVICE_NAME"
      exit 1
    fi
    printf "."
    sleep 2
  done
  echo ""
  ok "Service is healthy"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║                  Deploy complete                 ║"
echo "╚══════════════════════════════════════════════════╝"
if $BUILD_DOCKER; then
  echo "  UI:   http://10.10.10.2:$PORT"
  echo "  API:  http://10.10.10.2:$PORT/api"
  echo "  Logs: docker compose -f docker/compose.loadout.yml logs -f"
fi
echo ""
