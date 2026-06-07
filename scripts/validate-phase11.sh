#!/bin/bash
# Phase 11 validation: Verify code generation stack deployment
# Checks: OpenHands, vLLM, Ollama, models, configuration

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

# 1. vLLM responding
if curl -sf http://localhost:8000/v1/models > /dev/null 2>&1; then
    check_pass "vLLM API responding on :8000"
else
    check_fail "vLLM not responding on :8000"
fi

# 2. Ollama responding
if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    check_pass "Ollama responding on :11434"
else
    check_fail "Ollama not responding on :11434"
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
for file in configs/continue/config.json scripts/code-router.py; do
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

# 8. Python script syntax
if python3 -m py_compile scripts/code-router.py 2>/dev/null; then
    check_pass "code-router.py Python syntax valid"
else
    check_fail "code-router.py has syntax errors"
fi

# 9. Code models available in Ollama
QWEN_7B=$(curl -s http://localhost:11434/api/tags | grep -c "qwen2.5-coder:7b" || true)
QWEN_14B=$(curl -s http://localhost:11434/api/tags | grep -c "qwen2.5-coder:14b" || true)
QWEN_32B=$(curl -s http://localhost:11434/api/tags | grep -c "qwen2.5-coder:32b" || true)
DEEPSEEK=$(curl -s http://localhost:11434/api/tags | grep -c "deepseek-coder" || true)

if [ "$QWEN_7B" -gt 0 ] || [ "$QWEN_14B" -gt 0 ]; then
    check_pass "At least one Qwen coder model available in Ollama"
else
    check_warn "No Qwen coder models found (pull with: docker exec ollama ollama pull qwen2.5-coder:7b)"
fi

# 10. Verify vLLM can handle code requests
if curl -sf -X POST http://localhost:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "current-model", "prompt": "def hello(): ", "max_tokens": 10}' > /dev/null 2>&1; then
    check_pass "vLLM accepts code completion requests"
else
    check_warn "vLLM completion test failed (might be loading model)"
fi

echo ""
echo "Automated checks: $PASSED passed, $FAILED failed"
echo ""

# ========== MANUAL CHECKS ==========
echo "Manual verification checklist:"
echo ""
echo "[ ] Code models pulled in Ollama:"
echo "    docker exec ollama ollama list | grep qwen"
echo ""
echo "[ ] Continue.dev installed in IDE:"
echo "    VS Code: code --list-extensions | grep -i continue"
echo "    OR verify in IDE Extensions marketplace"
echo ""
echo "[ ] Continue.dev config in place:"
echo "    ~/.continue/config.json exists and is valid JSON"
echo ""
echo "[ ] Tab autocomplete working:"
echo "    Type incomplete Python: 'def hello():'  (should suggest) <press Tab>"
echo "    Should trigger suggestions from Qwen 7B (<100ms response)"
echo ""
echo "[ ] Code chat working:"
echo "    Ctrl+L (VS Code) → Select code → Ask: 'Explain this'"
echo "    Should generate explanation from primary model"
echo ""
echo "[ ] Slash commands available:"
echo "    Ctrl+L → Type: /security-review"
echo "    Should show command in autocomplete"
echo ""
echo "[ ] Model routing script working:"
echo "    python3 scripts/code-router.py"
echo "    Should output test cases with model recommendations"
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
echo "[ ] CUDA-specific routing:"
echo "    Test: /cuda-review on a CUDA kernel file"
echo "    Should route to larger model with CUDA-specific prompt"
echo ""

# ========== VLLM MODEL CHECK ==========
echo ""
echo "vLLM loaded models:"
curl -s http://localhost:8000/v1/models 2>/dev/null | jq '.data[].id' 2>/dev/null || check_warn "Could not query vLLM models"

echo ""
echo "Ollama available models:"
curl -s http://localhost:11434/api/tags 2>/dev/null | jq '.models[].name' 2>/dev/null | head -5 || check_warn "Could not query Ollama models"

# ========== RESULT ==========
echo ""
if [ $FAILED -eq 0 ]; then
    echo "Phase 11 READY ✓"
    exit 0
else
    echo "Phase 11 has $FAILED issue(s) — see above"
    exit 1
fi
