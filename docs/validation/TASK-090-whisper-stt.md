# TASK-090 — Validate Whisper STT API returns correct transcriptions

**Issue:** #36
**Result: PARTIAL / model mismatch** — the service is up and serving, but **not the
model the spec calls for**.

## Verified

`GET http://localhost:9099/v1/models` returns HTTP 200:

```json
{"data":[{"id":"Systran/faster-whisper-small","created":1700733231,
          "object":"model","owned_by":"Systran","language":["en","zh","de","es","ru", ...]}]}
```

The container is up on host port 9099 and the OpenAI-compatible model endpoint
answers.

## The discrepancy

`docker/compose.voice.yml:6-29` specifies model **`large-v3`**. The running service
reports **`Systran/faster-whisper-small`**.

`small` is roughly 40x smaller than `large-v3` and materially less accurate,
particularly on accented speech, domain vocabulary and noisy input. Any transcription
accuracy assessment made against this deployment is measuring the wrong model, so the
task's core question — "are transcriptions correct?" — cannot be answered as specified
until the intended model is loaded.

## Not covered

Submitting a generated WAV to `/v1/audio/transcriptions` is a non-mutating inference
call and within remit, but was not reached before SSH access to the host became
intermittent. Deferred rather than assumed.

## Verdict

Service health passes; model provenance fails. Resolve the `large-v3` vs `small`
mismatch first, then re-run the transcription accuracy check.

## Resolution

Static analysis only; the live host was not reachable. Re-verify on the host (see
below).

**Two separate findings, one of which corrects this document.**

1. **The "model mismatch" was a misreading of `/v1/models`.** In the pinned image
   (`fedirz/faster-whisper-server:latest-cuda`, last built 2024-10-01 from upstream
   `caba05a`, i.e. v0.5.0) `GET /v1/models` is not "the loaded model". It queries the
   Hugging Face Hub for every CTranslate2 ASR model and sorts by download count. The
   first entry is `Systran/faster-whisper-small` (the most downloaded; `created`
   1700733231 matches that repo). The active model is `config.whisper.model`, which
   `whisper-1` requests and requests with no `model` field resolve to.
2. **`docker/compose.voice.yml` was nonetheless wrong.** The image reads nested
   settings with a double underscore (`WHISPER__MODEL`, pydantic
   `env_nested_delimiter="__"`). The file used `WHISPER_MODEL`,
   `WHISPER_INFERENCE_DEVICE` and `WHISPER_COMPUTE_TYPE`, all silently ignored, and
   `large-v3` is not the spelling the server expects (it takes the HF repo id).
   `WHISPER_BEAM_SIZE`, `WHISPER_LANGUAGE` and `WHISPER_VAD_FILTER` are not settings
   in this version at all. The deployment would only have ended up on large-v3
   because the image's `Dockerfile.cuda` itself sets
   `WHISPER__MODEL=Systran/faster-whisper-large-v3`.

Fixed in `docker/compose.voice.yml`: `WHISPER__MODEL=Systran/faster-whisper-large-v3`,
`WHISPER__INFERENCE_DEVICE=cuda`, `WHISPER__COMPUTE_TYPE=float16`,
`DEFAULT_LANGUAGE=en`; dropped the unsupported beam-size and VAD variables (VAD is a
per-request `vad_filter` form field). Healthcheck moved from `curl .../v1/models` to
`/health` via `python3.12` (curl is not guaranteed in the nvidia/cuda base).
`loadout-manager/api/voice.py` `/voice/status` likewise probes `/health`.

The model cache mount `/data/models/whisper:/root/.cache/huggingface` is correct
(HF cache is `$HF_HOME/hub`). Budget about 3 GB for large-v3. Models stay loaded for
300 s after the last request (`WHISPER__TTL`), then unload from the GPU.

### To confirm on the host after redeploy

- `docker exec whisper env | grep -E 'WHISPER|DEFAULT_LANGUAGE'`
- `curl -s http://localhost:9099/api/ps` after one transcription request lists the
  loaded model (expect `Systran/faster-whisper-large-v3`).
- `nvidia-smi` shows about 3-6 GB held on GPU 0 while loaded.
- Then run the deferred `/v1/audio/transcriptions` accuracy check.
