#!/usr/bin/env bash
# Deploy Phase 07: Training Pipeline
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/container-helpers.sh
source "$REPO_ROOT/scripts/lib/container-helpers.sh"

echo "=== Phase 07: Training Pipeline Deploy ==="
echo ""

# ── 1. Verify Loadout Manager ─────────────────────────────────────────────────
echo "[1/4] Checking Loadout Manager..."
if ! curl -sf http://localhost:8800/health &>/dev/null; then
    echo "  ✗ Loadout Manager not running — deploy Phase 06 first"
    exit 1
fi
echo "  ✓ Loadout Manager running at :8800"

# ── 2. Setup storage ──────────────────────────────────────────────────────────
echo "[2/4] Setting up dataset and checkpoint directories..."
bash "$REPO_ROOT/scripts/setup-storage-phase07.sh"

# ── 3. Verify training compose file ───────────────────────────────────────────
echo "[3/4] Verifying docker compose file..."
if [[ ! -f "$REPO_ROOT/docker/compose.training.yml" ]]; then
    echo "  ✗ docker/compose.training.yml not found"
    exit 1
fi
docker compose -f "$REPO_ROOT/docker/compose.training.yml" config > /dev/null || {
    echo "  ✗ docker/compose.training.yml is invalid"
    exit 1
}
echo "  ✓ Compose file valid"

# ── 4. Start services ─────────────────────────────────────────────────────────
echo "[4/4] Starting training services (Label Studio, JupyterLab)..."
remove_orphan label-studio ai-training
remove_orphan jupyterlab ai-training
docker compose -f "$REPO_ROOT/docker/compose.training.yml" up -d label-studio jupyterlab
echo "  Waiting for startup (10s)..."
sleep 10

# Verify startup
if curl -sf http://localhost:8081 &>/dev/null; then
    echo "  ✓ Label Studio running at http://10.10.10.2:8081"
else
    echo "  ⚠  Label Studio not responding yet — check: docker logs label-studio"
fi

if curl -sf http://localhost:8888 &>/dev/null; then
    echo "  ✓ JupyterLab running at http://10.10.10.2:8888"
else
    echo "  ⚠  JupyterLab not responding yet — check: docker logs jupyterlab"
fi

echo ""
echo "=== Deploy complete ==="
echo ""
echo "Next steps:"
echo ""
echo "1. Upload training data:"
echo "   - Images: /data/datasets/images/raw/"
echo "   - Text: /data/datasets/text/raw/"
echo ""
echo "2. Image LoRA workflow:"
echo "   - Activate Loadout Manager profile: curl -X POST http://localhost:8800/activate/training-lora-image"
echo "   - Access Kohya at http://10.10.10.2:7860"
echo "   - Tag images with WD14 tagger or use Label Studio"
echo "   - Configure TOML file at configs/kohya/sdxl_lora.toml"
echo "   - Start training from Kohya UI"
echo ""
echo "3. Text LoRA workflow:"
echo "   - Prepare Alpaca format dataset in /data/datasets/text/formatted/"
echo "   - Activate profile: curl -X POST http://localhost:8800/activate/training-lora-text"
echo "   - Run: docker compose -f docker/compose.training.yml --profile training run axolotl accelerate launch -m axolotl.cli.train configs/axolotl/qlora_4gpu.yml"
echo ""
echo "4. Label Studio (annotation):"
echo "   - http://10.10.10.2:8081"
echo "   - Default: admin@local.dev / changeme"
echo "   - Create project with Image Captioning template"
echo "   - Import images from /data/datasets/images/raw/"
echo ""
echo "5. JupyterLab (experimentation):"
echo "   - http://10.10.10.2:8888"
echo "   - Token: check 'docker logs jupyterlab' for URL with token"
echo ""
echo "Troubleshooting:"
echo "  - Check GPU assignment: docker inspect kohya | grep NVIDIA_VISIBLE_DEVICES"
echo "  - Monitor training: docker logs -f kohya"
echo "  - Free GPUs: curl -X POST http://localhost:8800/stop"
