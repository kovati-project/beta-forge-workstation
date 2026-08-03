# TASK-102 — Validate Continue.dev connects to local inference endpoints

**Issue:** #41
**Result: FAIL** — every configured endpoint is unreachable, and four of the five
models are not present on the host.

## Configured in `configs/continue/config.json`

| Role | Model | apiBase |
| --- | --- | --- |
| Primary | `current-model` | `http://10.10.10.2:8000/v1` |
| Debug | `deepseek-coder-v2:16b` | `http://10.10.10.2:11434` |
| Architect | `large-model` | `http://10.10.10.2:8002/v1` |
| Fast | `qwen2.5-coder:14b` | `http://10.10.10.2:11434` |
| Autocomplete | `qwen2.5-coder:7b` | `http://10.10.10.2:11434` |
| Embeddings | `nomic-embed-text` | — |

The issue's claim that the autocomplete model matches the plan spec is accurate.

## Failure 1 — every apiBase is unroutable

All six entries point at `10.10.10.2`, which this host does not hold (see #32).
Continue.dev cannot reach any of them regardless of model availability.

## Failure 2 — the models mostly do not exist

`GET /api/tags` on Ollama returns exactly one model:

```
nomic-embed-text:latest
```

So of the three Ollama-backed roles — Debug, Fast, Autocomplete — **none** of the
referenced models is pulled. Only the embeddings model is present.

On the vLLM side, `current-model` **is** served (`localhost:8000/v1/models` confirms
it, `max_model_len` 16384), so the Primary role would work once the address is fixed.
`large-model` on port 8002 is not running — 8002 is absent from the listening set —
so the Architect role has no backend at all.

## Net effect

| Role | After fixing the IP | Fully working |
| --- | --- | --- |
| Primary | yes | yes |
| Debug | no — model not pulled | no |
| Architect | no — vllm-4gpu not running | no |
| Fast | no — model not pulled | no |
| Autocomplete | no — model not pulled | no |
| Embeddings | yes | yes |

Fixing #51 alone recovers 2 of 6. The other four additionally need
`ollama pull` for three models and the `inference-4gpu` profile running.

## Verdict

Fails on two independent axes. Address rewrite is necessary but not sufficient.
