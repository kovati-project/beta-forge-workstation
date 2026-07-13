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
