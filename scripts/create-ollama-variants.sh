#!/bin/bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: this script needs bash - run: bash $0" >&2; exit 1; }
# Creates Ollama model tags with long-context parameters baked in.
#
#   bash scripts/create-ollama-variants.sh                      # on the host
#   OLLAMA_URL=http://192.168.1.102:11434 bash scripts/create-ollama-variants.sh
#
# Why a tag instead of OLLAMA_CONTEXT_LENGTH: that variable is the default for
# every model, and clients that send no num_ctx (OpenHands over /v1) get it.
# Raising it to 128k would also size gpt-oss and the autocomplete model at 128k
# and overflow GPU1+GPU2. A tag gives only the agent model the long window.
#
# A tag shares the base model's weight blobs, so it costs no disk or download.
# Clients must all use the same tag and the same num_ctx: Ollama reloads the
# model whenever a request's num_ctx differs from the loaded one.
#
# qwen3-coder:30b-128k  (measured on 2x A5500, q8_0 KV, flash attention)
#   num_ctx 131072  - within the model's native 256k window, no rope scaling
#   num_batch 1024  - 120k-token prefill 2,113 tok/s vs 1,870 at the default
#                     512, for +1.2 GB; 2048 gave 2,253 tok/s for +3.6 GB
#   ~26 GB VRAM with OLLAMA_NUM_PARALLEL=1 (33 GB with 2 slots)

set -euo pipefail

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"

create_variant() {
    local name="$1" from="$2" params="$3"
    if ! curl -sf "$OLLAMA_URL/api/show" -d "{\"model\":\"$from\"}" > /dev/null; then
        echo "  SKIP $name: base model $from missing (docker exec ollama ollama pull $from)"
        return 1
    fi
    local out
    out=$(curl -sf "$OLLAMA_URL/api/create" \
        -d "{\"model\":\"$name\",\"from\":\"$from\",\"parameters\":$params,\"stream\":false}")
    if [[ "$out" == *'"success"'* ]]; then
        echo "  OK   $name (from $from, $params)"
    else
        echo "  FAIL $name: $out"
        return 1
    fi
}

echo "Creating Ollama model variants on $OLLAMA_URL"
status=0
create_variant "qwen3-coder:30b-128k" "qwen3-coder:30b" '{"num_ctx":131072,"num_batch":1024}' || status=1
exit $status
