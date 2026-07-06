# TASK-030 — Confirm Tools panel exists and enumerate implemented vs spec

**Issue:** #20
**Result: PASS** — the panel exists and is more complete than the Session-03 spec
described. The stale assumption was the Ph06 minimal UI.

## What exists

`ui/src/pages/Tools.jsx` renders `ServiceGroup` blocks driven by `SERVICE_GROUPS`
(`ui/src/utils/serviceRegistry.js`) — **9 groups covering 33 services**:

| Group | Services |
| --- | --- |
| Text Inference | vllm-pair-a, ollama, vllm-pair-b, vllm-4gpu |
| Image Studio | comfyui, invokeai, rembg |
| Training | kohya, axolotl, unsloth, label-studio, jupyterlab |
| Agentic & Workflow | n8n, dify, openhands, mcp-filesystem, mcp-browser, mcp-code-exec, mcp-fetch |
| Voice I/O | whisper-stt, piper-tts |
| Chat UI | open-webui, searxng |
| Storage & Vector | minio, qdrant, postgres, langfuse |
| Observability | prometheus, grafana, dcgm-exporter, node-exporter, cadvisor |
| Auth & Security | authentik |

## Spec item by item

The spec asked for *per-service controls, log streaming, container lifecycle management*.

| Spec item | Status | Where |
| --- | --- | --- |
| Per-service controls | **Implemented** | `Tools.jsx:11` `handleToggleService`, refetches `/api/services` after each toggle |
| Container lifecycle | **Partial** | `POST /api/services/{name}/start` (`services.py:181`) and `/stop` (`services.py:259`). **No restart route** — a restart is two round trips |
| Log streaming | **Backend only** | `GET /services/{name}/logs/stream` (`services.py:293-309`) is a real SSE endpoint (`StreamingResponse`, `text/event-stream`, `container.logs(stream=True, follow=True)`) — but the UI never calls it |
| Status display | Implemented | `ServiceCard.jsx:123-124` colour-codes starting / degraded / error / stopped |
| Inline logs | Implemented | `ServiceCard.jsx:17` fetches `/api/services/{name}/logs?n=100` on expand |

## Gaps

1. **SSE log streaming is built but unwired.** `ServiceCard` uses the static
   `?n=100` fetch; the streaming endpoint has no frontend consumer. This is exactly
   the scope of #21 — and confirms that issue's premise that the endpoint already
   exists and only needs wiring.
2. **No restart control.** Only start and stop exist, backend and frontend.
3. **No log export.** The inline view is capped at 100 lines with no way to get more
   out of the UI — the scope of #55.

## Verdict

Passes. The Tools panel exists, covers all 33 registered services across 9 groups,
and implements per-service controls, status and inline logs. The two real gaps are
already tracked as #21 and #55; the missing restart control is not currently tracked.
