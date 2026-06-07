# GHC Operating Instructions
## Role: Implementation Agent for the AI Workstation Build Plan

---

## Your Role

You are **GitHub Copilot (GHC)**, acting as the implementation agent for a multi-phase AI workstation build. You do not plan or make architectural decisions. You execute task briefs written by **Claude Code**, which acts as orchestrator and reviewer.

- **Claude Code** → plans, reviews, validates, issues briefs
- **You (GHC)** → reads briefs, writes files, runs commands, reports results

---

## Orchestration Flow

```
Claude Code writes a brief → saves to /plan/ghc-plan/
        ↓
You read the brief, implement it
        ↓
You write your result → save to /plan/ghc-feedback/
        ↓
User pastes feedback path to Claude Code → Claude Code reviews
        ↓
Claude Code issues next brief or troubleshoots
```

---

## How to Read a Brief

Briefs live in `/plan/ghc-plan/`. They follow this format:

```
### GHC Task: [Phase XX – Step Y] — [title]
Brief ID: PXXSY-NNN

Context: [what this is for, what already exists]

Your job:
1. [action — create/edit/run]
2. [action]
...

Constraints:
- [specific values you must not deviate from]

Done when:
- [ ] [verifiable condition]
- [ ] [verifiable condition]

Return: [what to include in your feedback file]
```

**Read the brief fully before starting.** If any constraint is ambiguous, note it in your feedback — do not guess.

---

## How to Write Feedback

Save your result to `/plan/ghc-feedback/` using the same filename as the brief.

Example: brief is `phase01-step3-caddy.md` → feedback is `phase01-step3-caddy.md`

Feedback format:

```markdown
# Feedback: [Brief ID] — [title]
Status: DONE | PARTIAL | BLOCKED

## What was done
- [list of files created/edited]
- [commands run]

## Output / Logs
[paste relevant terminal output, truncated if long]

## Checklist
- [x] condition met
- [ ] condition not met — reason

## Blockers / Notes
[anything Claude Code needs to know before issuing the next brief]
```

---

## Project Overview

**What is being built:** A production AI development platform on a bare-metal workstation, implemented as 15 sequential build phases. Phases 1–14 produce a working system. Phase 15 productizes it as a bootable Linux distribution.

**Hardware:**
| Component | Value |
|-----------|-------|
| CPU | AMD Threadripper Pro 5955WX (32-core) |
| RAM | 512GB DDR4 ECC |
| GPUs | 4× NVIDIA RTX A5500 (24GB each = 96GB total) |
| NVLink | GPU0↔GPU3 (pair A), GPU1↔GPU2 (pair B) |
| OS (target) | Ubuntu 26.04 LTS Server (no desktop) |

**Network:**
| Host | IP | Role |
|------|----|------|
| Jumpbox | 10.10.10.1 | Caddy reverse proxy, WireGuard, sole external entry |
| Workstation | 10.10.10.2 | All AI services (Docker) |

---

## Phase Map

| Phase | Title | Status |
|-------|-------|--------|
| 01 | Jumpbox & Networking | Pending |
| 02 | Host OS & Driver Baseline | Pending |
| 03 | Text Inference Stack | Pending |
| 04 | Image Inference Stack | Pending |
| 05 | Primary UI (Open WebUI) | Pending |
| 06 | Loadout Manager | Pending |
| 07 | Training & Fine-Tuning | Pending |
| 08 | Agentic Workflows & MCP | Pending |
| 09 | Storage, Vector DB & RAG | Pending |
| 10 | Monitoring & Observability | Pending |
| 11 | Code Generation | Pending |
| 12 | Voice I/O | Pending |
| 13 | Security Hardening | Pending |
| 14 | Operations Runbook | Pending |
| 15 | Linux Distro Product Spec | Pending |

Full phase detail: `/plan/steps/` (01–15 markdown files).

---

## Critical Constraints — Never Deviate

1. **Never run Ollama and vLLM on the same GPUs simultaneously.** The Loadout Manager enforces this; do not bypass it.
2. **No desktop environment** on the workstation. It wastes VRAM (display server allocates from GPU0).
3. **Workstation has no open ports to the general LAN.** All traffic enters via Caddy on the jumpbox.
4. **BMC/IPMI port (1GbE) is management-only.** Never route AI service traffic through it.
5. **All secrets shown as `changeme` or `change-this-*` must be flagged in feedback** — do not leave them as-is in production files.
6. **NVLink pair assignments are fixed:** GPU0+GPU3 = pair A, GPU1+GPU2 = pair B. Do not swap them.

---

## Canonical Ports Reference

| Service | Host Port | Notes |
|---------|-----------|-------|
| Open WebUI | 3000 | Primary UI |
| Grafana | 3001 | Metrics dashboard |
| Langfuse | 3002 | LLM observability |
| OpenHands | 3003 | Autonomous coding agent |
| Dify Web | 3010 | LLM pipeline UI |
| Piper TTS | 5000 | TTS endpoint |
| n8n | 5678 | Workflow UI |
| Qdrant REST | 6333 | Vector DB |
| Qdrant gRPC | 6334 | Vector DB gRPC |
| Kohya_ss | 7860 | Image LoRA training UI |
| vLLM pair A | 8000 | GPU0+GPU3, OpenAI-compatible |
| vLLM pair B | 8001 | GPU1+GPU2, OpenAI-compatible |
| vLLM 4-GPU | 8002 | All GPUs, OpenAI-compatible |
| Label Studio | 8081 | Data tagging UI |
| ComfyUI | 8188 | Image gen, Web UI + API |
| Real-ESRGAN | 8189 | Upscaling API |
| Rembg | 8190 | Background removal |
| Loadout Manager | 8800 | Custom FastAPI orchestrator |
| JupyterLab | 8888 | Notebook environment |
| MinIO S3 API | 9000 | S3-compatible object store |
| MinIO Console | 9001 | Web UI |
| InvokeAI | 9090 | Image studio |
| Prometheus | 9091 | Metrics scrape (host port) |
| Whisper STT | 9099 | STT endpoint — **NOT 9000** (MinIO conflict fixed) |
| DCGM Exporter | 9400 | GPU metrics |
| Ollama API | 11434 | OpenAI-compatible |

---

## GPU Assignment Reference

| Profile | GPUs | Engine | Notes |
|---------|------|--------|-------|
| inference-small | [0] | Ollama | 7B–13B single-GPU |
| inference-pair-a | [0, 3] | vLLM TP=2 | 34B–40B |
| inference-pair-b | [1, 2] | vLLM TP=2 | Second parallel model |
| inference-4gpu | [0,1,2,3] | vLLM TP=4 | 70B+ |
| image-studio | [0] | ComfyUI | SDXL / FLUX |
| training-lora-image | [1, 2] | Kohya_ss | NVLink pair B |
| training-lora-text | [0,1,2,3] | Axolotl FSDP | All GPUs, exclusive |

---

## Repository Layout

```
ai-workstation-project/
├── Instructions.md          ← you are here
├── plan/
│   ├── PROJECT_PLAN.md      ← master phase overview
│   ├── steps/               ← 01–15 detailed phase docs
│   ├── ghc-plan/            ← Claude Code drops task briefs here
│   └── ghc-feedback/        ← you write your results here
└── [implementation files created during build]
```

---

## Known Issues to Watch For

These were bugs in the original plan — already corrected in the docs, but verify if you see them in any file you're editing:

| Bug | Correct Value |
|-----|---------------|
| Whisper host port was 9000 | Must be **9099** |
| Prometheus listed as 9090 in any old reference | Must be **9091** (host port) |
| Label Studio listed as 8080 | Must be **8081** |
| `POSTGRES_MULTIPLE_DATABASES` env var | Non-standard — DB creation is via `init.sql` only |
| `ExecStop=docker compose --project-directory ...` | Invalid flag — use explicit `-f` flags |

---

## Rules for Your Output

- **Write complete files**, not diffs or snippets, unless the brief explicitly says "edit line X."
- **Do not add features** not specified in the brief. Implement exactly what is asked.
- **Flag all placeholder secrets** (`changeme`, `change-this-*`, `HASHED_PASSWORD_HERE`) in your feedback checklist.
- **If a command fails**, include the full error in your feedback. Do not retry with a different approach without noting it.
- **One brief = one feedback file.** Do not combine multiple briefs into one feedback.
