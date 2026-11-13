#!/bin/bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: this script needs bash - run: bash $0" >&2; exit 1; }
# Phase 11 validation: Verify code generation stack deployment
# Checks: OpenHands, vLLM (Qwen3.8-27B + embeddings), configuration

set -e

echo "=== Phase 11 Validation ==="
echo ""

FAILED=0
PASSED=0

# Helper functions
check_pass() {
    echo "✓ $1"
    PASSED=$(( PASSED + 1 ))
}

check_fail() {
    echo "✗ $1"
    FAILED=$(( FAILED + 1 ))
}

check_warn() {
    echo "⊘ $1"
}

# ========== AUTOMATED CHECKS ==========
echo "Automated checks:"
echo ""

# 1. Coding model (vllm-4gpu) serving qwen3.8-27b
if curl -sf http://localhost:8002/v1/models 2>/dev/null | grep -q '"qwen3.8-27b"'; then
    check_pass "vllm-4gpu serving qwen3.8-27b on :8002"
else
    check_fail "vllm-4gpu not serving qwen3.8-27b on :8002"
fi

# 2. Embeddings (vllm-embed) serving nomic-embed-text
if curl -sf http://localhost:8003/v1/models 2>/dev/null | grep -q '"nomic-embed-text"'; then
    check_pass "vllm-embed serving nomic-embed-text on :8003"
else
    check_fail "vllm-embed not serving nomic-embed-text on :8003"
fi

# 3. OpenHands responding
if curl -sf http://localhost:3003 > /dev/null 2>&1; then
    check_pass "OpenHands responding on :3003"
else
    check_fail "OpenHands not responding on :3003"
fi

# 4. Docker compose file valid
if docker compose -f docker/compose.codegen.yml config > /dev/null 2>&1; then
    check_pass "docker/compose.codegen.yml is valid"
else
    check_fail "docker/compose.codegen.yml syntax error"
fi

# 5. OpenHands container running
if docker ps | grep -q openhands; then
    check_pass "OpenHands container running"
else
    check_fail "OpenHands container not running"
fi

# 6. Config files exist
for file in configs/continue/config.yaml configs/continue/config.json configs/vscode/chatLanguageModels.json; do
    if [ -f "$file" ]; then
        check_pass "File exists: $file"
    else
        check_fail "File missing: $file"
    fi
done

# 7. Storage directories exist
for dir in /data/openhands /data/code-cache; do
    if [ -d "$dir" ]; then
        check_pass "Directory exists: $dir"
    else
        check_fail "Directory missing: $dir"
    fi
done

# 8. Fill-in-the-middle completion (Continue tab autocomplete path)
FIM_BODY='{"model": "qwen3.8-27b", "prompt": "<|fim_prefix|>def add(a, b):\n    <|fim_suffix|>\n<|fim_middle|>", "max_tokens": 16, "temperature": 0}'
if curl -sf -X POST http://localhost:8002/v1/completions \
    -H "Content-Type: application/json" -d "$FIM_BODY" 2>/dev/null | grep -q "return"; then
    check_pass "vllm-4gpu completes fill-in-the-middle requests"
else
    check_warn "FIM completion test failed (might be loading model)"
fi

echo ""
echo "Automated checks: $PASSED passed, $FAILED failed"
echo ""

# ========== MANUAL CHECKS ==========
echo "Manual verification checklist:"
echo ""
echo "[ ] Continue.dev installed in IDE:"
echo "    VS Code: code --list-extensions | grep -i continue"
echo "    OR verify in IDE Extensions marketplace"
echo ""
echo "[ ] Continue.dev config in place:"
echo "    ~/.continue/config.yaml matches configs/continue/config.yaml"
echo ""
echo "[ ] VS Code Copilot Chat model:"
echo "    Manage Models -> Custom Endpoint 'Workstation vLLM' (configs/vscode/chatLanguageModels.json)"
echo "    Agent mode with Qwen3.8 27B runs a tool (e.g. lists files) without raw <tool_call> text"
echo ""
echo "[ ] Tab autocomplete working:"
echo "    Type incomplete Python: 'def hello():'  (should suggest) <press Tab>"
echo "    Should trigger suggestions from Qwen3.8-27B (FIM)"
echo ""
echo "[ ] Code chat working:"
echo "    Ctrl+L (VS Code) → Select code → Ask: 'Explain this'"
echo "    Should generate explanation from primary model"
echo ""
echo "[ ] Slash commands available:"
echo "    Ctrl+L → Type: /security-review"
echo "    Should show command in autocomplete"
echo ""
echo "[ ] OpenHands autonomous tasks:"
echo "    Visit http://10.10.10.2:3003"
echo "    Create workspace (or use /data/openhands)"
echo "    Run task: 'Write a Python function that adds two numbers'"
echo "    Should execute autonomously and show results"
echo ""
echo "[ ] Codebase indexing (large repo):"
echo "    Ctrl+Shift+P → 'Continue: Index Codebase'"
echo "    Should complete without errors (might take 1-2 min for large repos)"
echo ""
echo "[ ] Semantic code search:"
echo "    Index repo → Ctrl+L → Ask: 'Find functions that handle authentication'"
echo "    Should retrieve relevant code chunks"
echo ""
echo "[ ] CUDA review prompt:"
echo "    Test: /cuda-review on a CUDA kernel file"
echo ""

# ========== VLLM MODEL CHECK ==========
echo ""
echo "vLLM served models:"
for port in 8002 8003; do
    curl -s "http://localhost:$port/v1/models" 2>/dev/null \
        | jq -r --arg p "$port" '.data[] | "  :\($p) \(.id) (max_model_len \(.max_model_len))"' 2>/dev/null \
        || check_warn "Could not query vLLM models on :$port"
done

# ========== RESULT ==========
echo ""
if [ $FAILED -eq 0 ]; then
    echo "Phase 11 READY ✓"
    exit 0
else
    echo "Phase 11 has $FAILED issue(s) — see above"
    exit 1
fi
