# GHC Task: Phase 04 — Image Inference Stack
**Brief ID:** P04-001  
**Source doc:** `/plan/steps/04-inference-image.md`  
**Write feedback to:** `/plan/ghc-feedback/phase04-inference-image.md`

---

## Context

Phases 01–03 are complete. The workstation (`adapress`, 10.10.10.2) is running:
- Ubuntu 26.04 LTS, driver 595.71.05, CUDA 13.3
- Docker with NVIDIA Container Runtime (default runtime = nvidia)
- Ollama running on GPU0 (port 11434)
- vLLM pair A available on GPU0+GPU3 (port 8000) — not always active

**GPU assignment convention for this phase:**
- GPU0 is the default image generation GPU
- GPU0 is shared between Ollama and ComfyUI — only one should hold it at a time
- The loadout manager (Phase 06) handles switching; for now deploy assuming GPU0 is free

This phase deploys ComfyUI as the primary image generation engine, with InvokeAI as an opt-in studio alternative. Rembg runs on CPU. Real-ESRGAN runs on GPU0.

---

## Scope

Create:
1. **`docker/compose.studio.yml`** — ComfyUI, InvokeAI (profiled), Real-ESRGAN, Rembg
2. **`scripts/setup-storage-phase04.sh`** — image model directory layout
3. **`scripts/deploy-phase04.sh`** — start services, print model download instructions
4. **`scripts/validate-phase04.sh`** — post-deploy checklist, exits non-zero on failure

**Not in scope:** model downloads (bandwidth-dependent, user does manually), Open WebUI integration (Phase 05), loadout switching (Phase 06).

---

## Step 1 — Storage Setup Script

Create `scripts/setup-storage-phase04.sh`:

```bash
#!/usr/bin/env bash
# Creates /data/ directories for image inference stack.
# Safe to re-run.
set -euo pipefail

sudo mkdir -p /data/models/comfyui/checkpoints
sudo mkdir -p /data/models/comfyui/loras
sudo mkdir -p /data/models/comfyui/vae
sudo mkdir -p /data/models/comfyui/controlnet
sudo mkdir -p /data/models/comfyui/embeddings
sudo mkdir -p /data/models/comfyui/upscale_models
sudo mkdir -p /data/models/invokeai
sudo mkdir -p /data/outputs/comfyui
sudo mkdir -p /data/outputs/invokeai
sudo mkdir -p /data/outputs/upscaled
sudo mkdir -p /data/outputs/rembg

sudo chown -R kasemo:kasemo /data/models/comfyui /data/models/invokeai /data/outputs

echo "Phase 04 storage layout created."
ls -la /data/models/ /data/outputs/
```

---

## Step 2 — Docker Compose: Image Stack

Create `docker/compose.studio.yml`:

```yaml
services:

  # ── ComfyUI: node-graph image generation ───────────────────────────────────
  # Primary image engine. GPU0 only. API-accessible for Open WebUI integration.
  # Custom nodes persist in a named volume so container updates don't wipe them.
  comfyui:
    image: ghcr.io/ai-dock/comfyui:latest-cuda
    container_name: comfyui
    restart: unless-stopped
    ports:
      - "8188:8188"
    volumes:
      - /data/models/comfyui/checkpoints:/opt/ComfyUI/models/checkpoints
      - /data/models/comfyui/loras:/opt/ComfyUI/models/loras
      - /data/models/comfyui/vae:/opt/ComfyUI/models/vae
      - /data/models/comfyui/controlnet:/opt/ComfyUI/models/controlnet
      - /data/models/comfyui/embeddings:/opt/ComfyUI/models/embeddings
      - /data/models/comfyui/upscale_models:/opt/ComfyUI/models/upscale_models
      - /data/outputs/comfyui:/opt/ComfyUI/output
      - comfyui-custom-nodes:/opt/ComfyUI/custom_nodes
    environment:
      - NVIDIA_VISIBLE_DEVICES=0
      - CLI_ARGS=--listen 0.0.0.0 --port 8188 --preview-method auto
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]

  # ── InvokeAI: professional studio UI ───────────────────────────────────────
  # Alternative to ComfyUI for canvas/inpainting workflows.
  # Gated behind "studio" profile — not started by default.
  # Do NOT run simultaneously with ComfyUI on GPU0.
  invokeai:
    image: ghcr.io/invoke-ai/invokeai:latest
    container_name: invokeai
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - /data/models/invokeai:/invokeai/models
      - /data/outputs/invokeai:/invokeai/outputs
      - invokeai-db:/invokeai/databases
    environment:
      - NVIDIA_VISIBLE_DEVICES=0
      - INVOKEAI_ROOT=/invokeai
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]
    profiles:
      - studio

  # ── Real-ESRGAN: upscaling API ──────────────────────────────────────────────
  realesrgan:
    image: pablogimenez/realesrgan-api:latest
    container_name: realesrgan
    restart: unless-stopped
    ports:
      - "8189:8000"
    volumes:
      - /data/outputs/upscaled:/app/output
    environment:
      - NVIDIA_VISIBLE_DEVICES=0
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]

  # ── Rembg: background removal (CPU) ────────────────────────────────────────
  rembg:
    image: danielgatis/rembg:latest
    container_name: rembg
    restart: unless-stopped
    ports:
      - "8190:5000"
    volumes:
      - /data/outputs/rembg:/app/output

volumes:
  comfyui-custom-nodes:
  invokeai-db:
```

---

## Step 3 — Deploy Script

Create `scripts/deploy-phase04.sh`:

```bash
#!/usr/bin/env bash
# Deploy Phase 04: Image Inference Stack
# Run on the workstation as kasemo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Phase 04: Image Inference Deploy ==="
echo ""

# ── 1. Storage check ──────────────────────────────────────────────────────────
echo "[1/3] Verifying storage layout..."
for dir in /data/models/comfyui/checkpoints /data/outputs/comfyui; do
    if [[ ! -d "$dir" ]]; then
        echo "  Missing: $dir — run scripts/setup-storage-phase04.sh first"
        exit 1
    fi
done
echo "  ✓ Storage directories present"

# ── 2. Start core services ────────────────────────────────────────────────────
echo "[2/3] Starting ComfyUI, Real-ESRGAN, Rembg..."
docker compose -f "$REPO_ROOT/docker/compose.studio.yml" up -d comfyui realesrgan rembg
echo "  Waiting for ComfyUI startup (30s)..."
sleep 30
if curl -sf http://localhost:8188/system_stats &>/dev/null; then
    echo "  ✓ ComfyUI running"
else
    echo "  ✗ ComfyUI not responding — check: docker logs comfyui"
    exit 1
fi

# ── 3. ComfyUI Manager ────────────────────────────────────────────────────────
echo "[3/3] Installing ComfyUI Manager..."
if docker exec comfyui test -d /opt/ComfyUI/custom_nodes/ComfyUI-Manager 2>/dev/null; then
    echo "  ✓ ComfyUI Manager already installed"
else
    docker exec comfyui bash -c "
        cd /opt/ComfyUI/custom_nodes && \
        git clone https://github.com/ltdrdata/ComfyUI-Manager && \
        pip install -q -r ComfyUI-Manager/requirements.txt
    " && docker restart comfyui && sleep 20 \
        && echo "  ✓ ComfyUI Manager installed" \
        || echo "  ✗ ComfyUI Manager install failed — check: docker logs comfyui"
fi

echo ""
echo "=== Deploy complete ==="
echo ""
echo "Model downloads (run manually — bandwidth-dependent):"
echo ""
echo "  SDXL base checkpoint:"
echo "    huggingface-cli download stabilityai/stable-diffusion-xl-base-1.0 \\"
echo "      --local-dir /data/models/comfyui/checkpoints/sdxl-base --include '*.safetensors'"
echo ""
echo "  SDXL VAE:"
echo "    huggingface-cli download madebyollin/sdxl-vae-fp16-fix \\"
echo "      --local-dir /data/models/comfyui/vae --include '*.safetensors'"
echo ""
echo "  Real-ESRGAN upscale model:"
echo "    wget -P /data/models/comfyui/upscale_models \\"
echo "      https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
echo ""
echo "  FLUX.1-dev (requires Black Forest Labs HF license):"
echo "    huggingface-cli download black-forest-labs/FLUX.1-dev \\"
echo "      --local-dir /data/models/comfyui/checkpoints/flux1-dev --include '*.safetensors'"
echo "    NOTE: FLUX.1-dev fills all 24GB of GPU0. Only use when LLM inference is idle."
echo ""
echo "  After downloading, install recommended custom nodes via ComfyUI Manager UI:"
echo "    http://10.10.10.2:8188 → Manager → Install Missing Custom Nodes"
echo "    Recommended: Impact Pack, Efficiency Nodes, ControlNet Aux, WAS Node Suite"
```

---

## Step 4 — Validate Script

Create `scripts/validate-phase04.sh`:

```bash
#!/usr/bin/env bash
# Run on the workstation after deploy-phase04.sh and at least one model download.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS=0; FAIL=0; WARN=0

check() {
    local desc="$1"; shift
    if eval "$@" &>/dev/null; then
        echo -e "${GREEN}✓${NC} $desc"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $desc"
        ((FAIL++))
    fi
}

warn() {
    echo -e "${YELLOW}?${NC} $1 — check manually"
    ((WARN++))
}

echo "=== Phase 04 Validation ==="
echo ""

# Core services
check "ComfyUI container running"      "docker ps --filter name=comfyui --filter status=running | grep -q comfyui"
check "ComfyUI API responding"         "curl -sf http://localhost:8188/system_stats"
check "Rembg container running"        "docker ps --filter name=rembg --filter status=running | grep -q rembg"
check "Rembg API responding"           "curl -sf http://localhost:8190/api/removebg -X POST 2>/dev/null || curl -sf http://localhost:8190/ 2>/dev/null"
check "Real-ESRGAN container running"  "docker ps --filter name=realesrgan --filter status=running | grep -q realesrgan"

# Models
echo ""
check "At least one ComfyUI checkpoint exists"  "ls /data/models/comfyui/checkpoints/ 2>/dev/null | grep -q '.'"
check "ComfyUI Manager installed"               "docker exec comfyui test -d /opt/ComfyUI/custom_nodes/ComfyUI-Manager"

# GPU assignment
echo ""
check "ComfyUI assigned to GPU0"  "docker inspect comfyui | grep -q '\"0\"'"

# Manual checks
echo ""
warn "ComfyUI web UI loads at http://10.10.10.2:8188"
warn "Checkpoint visible in ComfyUI model list (refresh browser)"
warn "Test generation completes — queue a simple txt2img and check /data/outputs/comfyui/"
warn "GPU0 VRAM shows 8–12GB during SDXL generation — check: nvidia-smi"
warn "InvokeAI NOT running by default (profiled) — verify: docker ps | grep invokeai"

echo ""
echo "Result: ${PASS} passed, ${FAIL} failed, ${WARN} manual checks"
[[ $FAIL -eq 0 ]] && echo -e "${GREEN}Phase 04 READY${NC}" || echo -e "${RED}Phase 04 NOT READY — fix failures above${NC}"
exit $FAIL
```

---

## Constraints

- **InvokeAI must be behind the `studio` profile** — it must not start by default. Only ComfyUI, Real-ESRGAN, and Rembg start on `docker compose up`.
- **ComfyUI and InvokeAI must never share GPU0 simultaneously.** The compose file achieves this via the profile gate. Flag this in feedback.
- **Rembg runs on CPU only** — no GPU reservation in its service definition.
- **Do not pin image tags** to specific versions other than `latest` — version pinning is a Phase 14 concern.
- **FLUX.1-dev requires a Black Forest Labs HF license.** The deploy script must print a warning about this, not attempt the download unconditionally.
- **Do not create a Caddy route for any port in this phase** — Phase 01 (Caddy) is tabled. All access is direct by IP.
- **`upscale_models` volume mount must be included** in the ComfyUI service — it is missing from the source doc and needed for Real-ESRGAN models loaded inside ComfyUI workflows.

---

## Done When

- [ ] `scripts/setup-storage-phase04.sh` created
- [ ] `docker/compose.studio.yml` created with all four services
- [ ] InvokeAI gated behind `studio` profile
- [ ] Rembg has no GPU reservation
- [ ] `scripts/deploy-phase04.sh` created — prints FLUX.1-dev license warning
- [ ] `scripts/validate-phase04.sh` created — exits non-zero on hard failures
- [ ] All files use Unix line endings (LF)

---

## Return to Claude

In your feedback file, include:
1. List of all files created with their paths
2. Confirm InvokeAI is behind profile and Rembg has no GPU reservation
3. Flag: is `upscale_models` volume mount present in the ComfyUI service?
4. Any deviations from the compose spec and why
5. Any blockers before Phase 05 can start
