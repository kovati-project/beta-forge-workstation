# TASK-091 — Validate Piper TTS returns playable audio

**Issue:** #37
**Result: FAIL as specified** — port 5000 is open but speaks no HTTP, and the repo
contradicts itself about which port and protocol Piper uses.

## Evidence

| Check | Result |
| --- | --- |
| Port 5000 in host listening set | present |
| `curl http://localhost:5000/` | HTTP code `000` — no HTTP response |

The socket accepts connections but returns nothing an HTTP client can parse.

## The discrepancy the issue asked us to resolve, resolved

The `ghcr.io/linuxserver/piper` image serves the **Wyoming** protocol, not HTTP.
Wyoming is a line-delimited JSON protocol over a raw TCP socket, which is exactly
what a `curl` against it looks like: connection succeeds, no HTTP response.

That reconciles the contradiction the issue flagged:

- `docker/compose.voice.yml:38-43` maps host `5000` to container `10200` — 10200
  is the Wyoming default, so the mapping is internally consistent.
- `loadout-manager/api/voice.py:78-79` and the container healthcheck treat the
  endpoint as HTTP — that is the incorrect half.

So the port mapping is right and the health probe is wrong. A Wyoming service will
never satisfy an HTTP healthcheck, which means Piper will report unhealthy
indefinitely even while working correctly.

## Consequence for Open WebUI

`docker/compose.webui.yml` configures TTS as an OpenAI-compatible HTTP endpoint
pointed at Piper. An OpenAI-compatible client cannot talk to a Wyoming socket, so
voice output cannot work as currently wired — relevant to #38.

## Verdict

Fails as specified, but the finding is a protocol mismatch rather than a dead service.
Either front Piper with an HTTP shim exposing an OpenAI-compatible speech endpoint, or
repoint the healthcheck and Open WebUI at something that speaks Wyoming.
