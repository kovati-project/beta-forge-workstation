# Phase 11 — Code Generation
[← Monitoring](10-monitoring.md) | [Next: Voice I/O →](12-voice-io.md)

---

## Objective
Configure the full code generation stack: Continue.dev as the IDE copilot, OpenHands as an autonomous coding agent, and model selection tuned for code quality across languages. All traffic routes through the local inference stack — zero cloud leakage.

---

## Model Recommendations for Code

| Model | Size | GPU Assignment | Strength |
|-------|------|----------------|----------|
| qwen2.5-coder:32b | 32B | vLLM pair A [0,3] | Primary: best overall code quality |
| qwen2.5-coder:14b | 14B | Ollama GPU1 | Tab completion, low latency |
| deepseek-coder-v2:16b | 16B | Ollama GPU1 | Strong at debugging and refactoring |
| codellama:70b | 70B | vLLM 4GPU | Large context, full repo analysis |
| qwen2.5-coder:7b | 7B | Ollama GPU0 | Fast autocomplete, <50ms |

---

## Step 1 — Pull Code Models via Ollama

```bash
docker exec ollama ollama pull qwen2.5-coder:32b
docker exec ollama ollama pull qwen2.5-coder:14b
docker exec ollama ollama pull qwen2.5-coder:7b
docker exec ollama ollama pull deepseek-coder-v2:16b
docker exec ollama ollama pull nomic-embed-text    # for codebase indexing
```

---

## Step 2 — Continue.dev Full Configuration

Install on every client machine (VS Code, JetBrains, or Neovim):

```bash
# VS Code
code --install-extension Continue.continue

# JetBrains (IntelliJ, PyCharm, etc.)
# Install via Marketplace: search "Continue"
```

Full `~/.continue/config.json`:

```json
{
  "models": [
    {
      "title": "Qwen2.5-Coder 32B [Primary]",
      "provider": "openai",
      "model": "current-model",
      "apiBase": "https://ai.local/vllm-a/v1/",
      "apiKey": "EMPTY",
      "contextLength": 32768,
      "completionOptions": {
        "temperature": 0.1,
        "maxTokens": 4096
      }
    },
    {
      "title": "DeepSeek Coder 16B [Debug]",
      "provider": "ollama",
      "model": "deepseek-coder-v2:16b",
      "apiBase": "https://ai.local/ollama/",
      "contextLength": 16384
    },
    {
      "title": "Llama 3.3 70B [Architect]",
      "provider": "openai",
      "model": "large-model",
      "apiBase": "https://ai.local/vllm-4gpu/v1/",
      "apiKey": "EMPTY",
      "contextLength": 16384
    }
  ],

  "tabAutocompleteModel": {
    "title": "Qwen2.5-Coder 7B [Fast]",
    "provider": "ollama",
    "model": "qwen2.5-coder:7b",
    "apiBase": "https://ai.local/ollama/",
    "contextLength": 4096
  },

  "embeddingsProvider": {
    "provider": "ollama",
    "model": "nomic-embed-text",
    "apiBase": "https://ai.local/ollama/"
  },

  "contextProviders": [
    {
      "name": "code",
      "params": {}
    },
    {
      "name": "docs",
      "params": {}
    },
    {
      "name": "diff",
      "params": {}
    },
    {
      "name": "terminal",
      "params": {}
    },
    {
      "name": "problems",
      "params": {}
    },
    {
      "name": "folder",
      "params": {}
    },
    {
      "name": "codebase",
      "params": {
        "nRetrieve": 25,
        "nFinal": 5,
        "useReranking": true
      }
    }
  ],

  "slashCommands": [
    {
      "name": "edit",
      "description": "Edit selected code"
    },
    {
      "name": "comment",
      "description": "Add inline documentation"
    },
    {
      "name": "tests",
      "description": "Generate unit tests"
    },
    {
      "name": "refactor",
      "description": "Refactor for clarity and performance"
    },
    {
      "name": "review",
      "description": "Security and quality code review"
    },
    {
      "name": "explain",
      "description": "Explain this code in depth"
    }
  ],

  "customCommands": [
    {
      "name": "security-review",
      "prompt": "Review this code for security vulnerabilities. Check for: injection flaws, authentication bypasses, insecure deserialization, sensitive data exposure, SSRF, and privilege escalation. Provide specific remediation for each finding.",
      "description": "Security-focused code review"
    },
    {
      "name": "optimize",
      "prompt": "Analyze this code for performance issues. Identify algorithmic complexity problems, unnecessary allocations, blocking calls, and optimization opportunities. Provide concrete improvements.",
      "description": "Performance analysis and optimization"
    },
    {
      "name": "document",
      "prompt": "Write comprehensive documentation for this code: function signatures, parameter descriptions, return values, exceptions, usage examples, and architectural notes where relevant.",
      "description": "Generate full documentation"
    }
  ]
}
```

---

## Step 3 — Codebase Indexing

Continue.dev can index your entire codebase for semantic search:

```bash
# In VS Code with Continue installed:
# Ctrl+Shift+P → "Continue: Index Codebase"
# This embeds your code via nomic-embed-text and stores locally

# For large repos (>100k files), pre-filter in config:
```

```json
{
  "codebaseContext": {
    "excludeDirs": [
      "node_modules", ".git", "dist", "build",
      "__pycache__", ".venv", "vendor"
    ],
    "excludeGlobs": ["*.min.js", "*.lock", "*.png", "*.jpg"]
  }
}
```

---

## Step 4 — OpenHands: Autonomous Coding Agent

OpenHands (formerly OpenDevin) is a fully local autonomous coding agent that can browse docs, write and run code, debug, and iterate.

```bash
cat <<'EOF' >> ~/ai-workstation/docker/compose.agentic.yml

  openhands:
    image: ghcr.io/all-hands-ai/openhands:latest
    container_name: openhands
    restart: unless-stopped
    ports:
      - "3003:3000"
    volumes:
      - /data/openhands:/opt/openhands/workspace
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - OPENAI_API_BASE=http://10.10.10.2:8000/v1
      - OPENAI_API_KEY=EMPTY
      - OPENAI_MODEL=current-model
      - SANDBOX_TYPE=local
      - WORKSPACE_MOUNT_PATH=/data/openhands

EOF

docker compose -f ~/ai-workstation/docker/compose.agentic.yml up -d openhands
# Access at http://10.10.10.2:3003
```

**OpenHands use cases:**
- "Implement this feature from the GitHub issue description"
- "Debug why this test is failing and fix the root cause"
- "Refactor this module to use async/await throughout"
- "Write a FastAPI endpoint for X with full test coverage"
- "Review this PR diff and suggest improvements"

---

## Step 5 — Code-Specific System Prompts

Configure in Open WebUI for code-focused chat sessions:

```
You are an expert software engineer with deep expertise in:
- Systems programming (Rust, C++, C)
- Cloud architecture (AWS, GCP, Kubernetes)
- Security engineering (threat modeling, secure code review, CVE analysis)
- AI/ML engineering (PyTorch, CUDA, distributed training)
- Data engineering (Spark, Kafka, dbt)

When reviewing code:
1. Check for correctness first
2. Identify security issues explicitly
3. Note performance implications
4. Suggest idiomatic improvements
5. Keep explanations concise unless asked to elaborate

Always include runnable examples when demonstrating fixes.
```

---

## Step 6 — Language-Specific Model Routing

Add to n8n or as an Open WebUI pipe — routes code requests to optimal models:

```python
"""Route code requests to the best model per language/task."""

ROUTING_RULES = {
    # Language → preferred model
    "rust":       "current-model",      # Qwen2.5-Coder 32B
    "python":     "current-model",
    "typescript": "current-model",
    "go":         "current-model",
    "cpp":        "current-model",
    "cuda":       "large-model",        # 70B for CUDA complexity
    
    # Task → preferred model
    "security":   "large-model",        # 70B for security review depth
    "architect":  "large-model",
    "autocomplete": "qwen2.5-coder:7b", # 7B for speed
}

def route_code_request(message: str, language: str = None) -> str:
    if language and language.lower() in ROUTING_RULES:
        return ROUTING_RULES[language.lower()]
    
    msg_lower = message.lower()
    for keyword, model in ROUTING_RULES.items():
        if keyword in msg_lower:
            return model
    
    return "current-model"  # default
```

---

## Validation Checklist

- [ ] `qwen2.5-coder:32b` pulled in Ollama and responding
- [ ] Continue.dev installed in VS Code, connected to local endpoints
- [ ] Tab autocomplete working (Qwen 7B, <100ms response)
- [ ] Codebase indexing completed for at least one project
- [ ] `/security-review` slash command working on sample code
- [ ] OpenHands accessible at `:3003`, connected to vLLM
- [ ] OpenHands completes a simple task (write a function, run tests)
- [ ] All code traffic stays local (verify no external API calls in network monitor)

---

## Notes
- Set `temperature: 0.1` for code generation — low temperature gives more deterministic, correct output
- The 7B model for tab autocomplete is a deliberate latency trade-off — anything larger adds perceptible lag that breaks the autocomplete feel
- OpenHands needs the Docker socket to spin up sandbox containers for code execution — treat it as a privileged service
- For CUDA kernel development specifically, the 70B model shows significantly better understanding of memory access patterns and occupancy than 32B
- Continue.dev's `codebase` context provider with `useReranking: true` dramatically improves relevance of retrieved code chunks for large repos
