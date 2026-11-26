# Known gaps as of 2026-11-14

The source of truth for open work is the
[GitHub project board](https://github.com/users/KasemOmary/projects/2) and the
open issues in kovati-project/beta-forge-workstation. This page is a dated
summary of them, grouped by `section:` label. It deliberately has no
completeness percentages; if it disagrees with the board, the board wins.

The 2026-06-06 audits it replaces are archived, and out of date, in
[plan/archive/](archive/).

## Open themes

- **Host validation backlog.** Most open issues are `TASK-0xx`/`TASK-1xx`
  validation tasks: the code exists but has not been verified end-to-end on the
  workstation (profile switching, training stack, voice, MCP servers, backup and
  restore, forward-auth).
- **Security hardening.** Deploying the secrets/backup/switch fixes and rotating
  leaked passwords, container hardening, and auth/RBAC.
- **Smaller enhancements.** Real alert notifications, model listing, and
  replacing hard-coded `10.10.10.2` addresses.

## Open issues by section

### section:security
- #75 Deploy secrets/backup/switch fixes to the host and rotate the leaked passwords
- #68 Harden containers: cap_drop, no-new-privileges, network isolation
- #61 TASK-113: Validate API key CRUD end-to-end
- #60 TASK-112: Validate Admin user CRUD end-to-end against live Authentik
- #54 Need auth and RBAC (Roles / Groups)
- #50 TASK-114: Validate Caddy forward-auth actually protects service endpoints end-to-end
- #43 TASK-111: Verify no services are running as root unnecessarily

### section:operations
- #59 TASK-123: Validate backup to restore end-to-end cycle via API
- #46 TASK-122: Run the NVLink validation script and document results
- #45 TASK-121: Validate the backup script runs successfully

### section:monitor
- #64 Configure a real AlertManager notification channel (receivers are no-ops)
- #31 TASK-063: Validate Langfuse is connected to Postgres and accessible
- #30 TASK-062: Validate Grafana dashboards and datasource
- #28 TASK-060: Validate Prometheus is scraping all targets successfully

### section:agentic
- #58 TASK-103: Validate MCP browser, code-exec, and fetch servers
- #41 TASK-102: Validate Continue.dev connects to local inference endpoints
- #40 TASK-101: Validate MCP filesystem server is accessible and sandboxed correctly
- #39 TASK-100: Validate n8n is functional and can call Ollama

### section:resources
- #53 Models not populated
- #27 TASK-052: Validate Open WebUI RAG pipeline end-to-end
- #26 TASK-051: Validate Qdrant collections and embedding pipeline
- #25 TASK-050: Validate MinIO bucket structure matches spec

### section:expose
- #51 Update all 10.10.10.2 references to use a resolvable hostname
- #33 TASK-071: Validate UFW rules are in place and correctly scoped

### section:voice
- #38 TASK-092: Validate Open WebUI voice mode end-to-end
- #37 TASK-091: Validate Piper TTS returns playable audio
- #36 TASK-090: Validate Whisper STT API returns correct transcriptions

### section:settings
- #35 TASK-081: Validate all default credentials have been changed
- #34 TASK-080: Validate Open WebUI admin settings are configured correctly

### section:training
- #24 TASK-042: Validate Label Studio is accessible and dataset mount is correct
- #23 TASK-041: Validate Axolotl config parses and NCCL initializes across all 4 GPUs
- #22 TASK-040: Validate Kohya_ss UI is reachable and GPU assignment is correct

### section:loadout
- #19 TASK-029: Validate image-studio profile (ComfyUI + vLLM pair-b co-existence)
- #18 TASK-028: Validate the dual-stack profile (simultaneous vLLM on both pairs)
- #17 TASK-027: Validate profile switch correctly tears down previous services
- #16 TASK-026: Validate incompatibility gate (training vs inference)
- #15 TASK-025: Validate VRAM conflict gate
- #14 TASK-024: End-to-end profile activation, inference-4gpu (70B path)
- #13 TASK-023: End-to-end profile activation, inference-pair-b (NVLink Bridge B)
- #12 TASK-022: End-to-end profile activation, inference-pair-a (NVLink Bridge A)
- #11 TASK-021: End-to-end profile activation, inference-small
- #10 TASK-020: Validate all 9 profiles render in the UI

### section:dashboard
- #8 TASK-013: Validate switching state display
- #7 TASK-012: Validate active profile display

### No section label
- #69 Small follow-ups from the Oct 2026 validation fix sweep

(#65, which asked for this page, is closed by the change that adds it.)
