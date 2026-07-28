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
