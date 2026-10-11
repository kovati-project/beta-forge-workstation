# TASK-060 — Validate Prometheus is scraping all targets successfully

**Issue:** #28
**Result: FAIL** — 7 of 11 targets are DOWN. Every failure is the same root cause.

## Evidence

`GET http://localhost:9091/api/v1/targets` — 11 active targets, **4 up / 7 down**:

| Job | Scrape URL | Error |
| --- | --- | --- |
| comfyui | `http://10.10.10.2:8188/metrics` | no route to host |
| loadout-manager | `http://10.10.10.2:8800/health` | context deadline exceeded |
| ollama | `http://10.10.10.2:11434/metrics` | context deadline exceeded |
| open-webui | `http://10.10.10.2:3000/metrics` | context deadline exceeded |
| vllm-4gpu | `http://10.10.10.2:8002/metrics` | context deadline exceeded |
| vllm-pair-a | `http://10.10.10.2:8000/metrics` | context deadline exceeded |
| vllm-pair-b | `http://10.10.10.2:8001/metrics` | context deadline exceeded |

## Root cause

All seven point at `10.10.10.2`, which is not an address this host holds.
`hostname -I` reports:

```
169.254.3.1  192.168.1.103  192.168.1.102  172.21.0.1  172.22.0.1
172.20.0.1   172.17.0.1     172.18.0.1     172.19.0.1
```

The workstation is on **192.168.1.102 / 192.168.1.103**; the `10.10.10.0/24` network
from the Ph03+ specs does not exist here. `configs/prometheus/prometheus.yml`
hardcodes the old address, so these scrapes can never succeed.

The four targets that are UP are the ones scraped by container name or localhost
rather than by that literal IP.

Note that several of these services *are* running and reachable on the correct
address — vllm-pair-a answers on `localhost:8000` (`/v1/models` returns
`current-model`), Ollama on 11434, loadout-manager on 8800. This is purely an
addressing fault, not a service outage.

## Verdict

Fails. Blocked on #51 / #32 — replacing the hardcoded `10.10.10.2` with a
resolvable name fixes all seven at once.

## Resolution

Branch `fix/prometheus-scrape-targets` (not yet deployed to the workstation).

Root cause was broader than the stale IP: Prometheus runs in a container, so a
host LAN address is the wrong frame of reference regardless of which IP is used.
Targets are now addressed from inside the container:

| Job | New target | Why |
| --- | --- | --- |
| ollama | `ollama:11434` | shares `ai-workstation` network |
| vllm-pair-a | `vllm-pair-a:8000` | shares `ai-workstation`; container port 8000 |
| vllm-pair-b | `vllm-pair-b:8000` | container port is 8000 (host 8001 is publish-only) |
| vllm-4gpu | `vllm-4gpu:8000` | container port is 8000 (host 8002 is publish-only) |
| comfyui | `comfyui:8188` | shares `ai-workstation` |
| open-webui | `open-webui:8080` | container port is 8080 (host 3000 is publish-only) |
| loadout-manager | `host.docker.internal:8800` | only on `ai-loadout`; prometheus gains `extra_hosts: host.docker.internal:host-gateway` |

Address fix alone does not make every target UP. Expected after deploy:

- **UP (when container running):** vllm-pair-a. vllm-pair-b / vllm-4gpu are
  profile-gated and mutually exclusive on GPUs, so they are UP only while their
  loadout is active (DNS failure otherwise is expected).
- **Still DOWN, endpoint does not exist:**
  - loadout-manager: `/health` is JSON, and there is no Prometheus-format
    endpoint in `loadout-manager/` (`/api/metrics/*` are JSON, no
    `prometheus_client`). Needs an exporter endpoint added; deliberately not
    done here.
  - ollama: stock Ollama serves no `/metrics`. Needs a sidecar exporter.
  - comfyui: stock ComfyUI serves no `/metrics`. Needs a custom node/exporter.
  - open-webui: no Prometheus pull endpoint in stock config (OTLP push only).
  - These four were not removed so alerting intent is preserved, but they
    will keep tripping the `ServiceDown` (`up == 0`) alert until an exporter
    is added or the jobs are dropped. Follow-up decision needed.

Not verified from the dev machine: live reachability, `host-gateway` resolution
on the workstation, and the Ollama/ComfyUI/Open WebUI `/metrics` claims (based on
upstream behaviour, not probed on the live containers). Verify with
`curl -s localhost:9091/api/v1/targets` after `docker compose -f
docker/compose.monitoring.yml up -d prometheus` and a Prometheus config reload.
If UFW is later enabled (TASK-071), allow docker bridge to host port 8800 or the
loadout-manager scrape will time out.
