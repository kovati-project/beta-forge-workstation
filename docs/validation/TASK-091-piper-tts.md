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

## Resolution

Static analysis only; the live host was not reachable.

- `docker/compose.voice.yml`: the Piper healthcheck is now `nc -z 127.0.0.1 10200`.
  This is the same readiness probe the image's own s6 service runs
  (`nc -z localhost 10200`), and `netcat-openbsd` is installed in the
  linuxserver baseimage. `start_period` raised to 120 s because first start downloads
  the voice before listening.
- `loadout-manager/api/voice.py`: `/voice/status` now checks Piper with a TCP connect
  (`asyncio.open_connection`, 3 s timeout) to the host/port parsed from `PIPER_URL`
  (overridable with `PIPER_HOST` / `PIPER_PORT`).
- Also in `compose.voice.yml`: the tuning variables were not the names the image
  reads (`PIPER_LENGTH_SCALE`, `PIPER_NOISE_SCALE`, `PIPER_NOISE_W` were ignored).
  Renamed to `PIPER_LENGTH`, `PIPER_NOISE`, `PIPER_NOISEW`. Note this makes
  `PIPER_NOISEW=0.8` take effect for the first time (image default is 0.333).

**Not fixed here:** `/voice/synthesize` and `/voice/voices` in `voice.py` still call
HTTP routes (`/api/tts`, `/api/voices`) that Piper does not have; they are marked as
known-broken in code. Open WebUI TTS (#38) is unchanged and still cannot reach Piper.
