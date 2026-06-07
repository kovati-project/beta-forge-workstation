#!/usr/bin/env bash
# Deploy Phase 04: Image Inference Stack
# Run on the workstation as kasemo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Phase 04: Image Inference Deploy ==="
echo ""

# ── Verify compose file exists ────────────────────────────────────────────────
if [[ ! -f "$REPO_ROOT/docker/compose.studio.yml" ]]; then
    echo "ERROR: Expected compose file at $REPO_ROOT/docker/compose.studio.yml"
    exit 1
fi

# ── 1. Storage check ──────────────────────────────────────────────────────────
echo "[1/3] Verifying storage layout..."
for dir in /data/models/comfyui/checkpoints /data/outputs/comfyui; do
    if [[ ! -d "$dir" ]]; then
        echo "  Running setup-storage-phase04.sh..."
        bash "$REPO_ROOT/scripts/setup-storage-phase04.sh"
        break
    fi
done
echo "  ✓ Storage directories present"

# ── 2. Start core services ────────────────────────────────────────────────────
echo "[2/3] Starting ComfyUI and Rembg..."
docker compose -f "$REPO_ROOT/docker/compose.studio.yml" up -d comfyui rembg
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
echo "    NOTE: FLUX.1-dev requires you to accept the license on Hugging Face."
echo "    If you do not have HF token with FLUX.1-dev access, visit:"
echo "      https://huggingface.co/black-forest-labs/FLUX.1-dev"
echo "    Accept the license, then:"
echo "    huggingface-cli login"
echo "    huggingface-cli download black-forest-labs/FLUX.1-dev \\"
echo "      --local-dir /data/models/comfyui/checkpoints/flux1-dev --include '*.safetensors'"
echo "    WARNING: FLUX.1-dev fills all 24GB of GPU0. Only use when LLM inference is idle."
echo ""
echo "  After downloading, install recommended custom nodes via ComfyUI Manager UI:"
echo "    http://10.10.10.2:8188 → Manager → Install Missing Custom Nodes"
echo "    Recommended: Impact Pack, Efficiency Nodes, ControlNet Aux, WAS Node Suite"
