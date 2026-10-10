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

## Alert rules

Follow-up audit of `configs/prometheus/alerts.yml` against what is actually
scraped. Several rules referenced metrics nothing in this estate emits, so they
could never fire. Checked statically (promtool, dcgm-exporter 3.3.6
`default-counters.csv`, vLLM 0.31 source); the live workstation was not reachable.

| Rule | Problem | Action |
| --- | --- | --- |
| `vLLMHighLatency` | `vllm_request_duration_seconds` does not exist; `histogram_quantile` was fed a raw series | Rewritten on `vllm:e2e_request_latency_seconds_bucket` with `rate()` and `sum by (le, ...)` |
| `OllamaQueueBuildup` | `ollama_queue_size`: stock Ollama exports no metrics | Disabled (commented, with what an exporter would need) |
| `TrainingCheckpointError` | `training_checkpoint_errors_total`: nothing in the repo emits it | Disabled (commented, with how to enable) |
| `PrometheusStorageHigh` | `mountpoint="/prometheus"` exists only inside the prometheus container | Disabled; `FilesystemCritical` covers the backing host filesystem |
| `NVLinkErrors` | wrong field name (`..._ERR_COUNT_TOTAL`); field also commented out in the default counters CSV | Name corrected; still needs a custom counters CSV to be exported |
| `GPUECCDoublebitError` | valid name, but commented out in the default counters CSV | Unchanged; documented as requiring a counters CSV (and ECC enabled on the card) |
| `CPUHighTemperature` | matched `chip=~".*coretemp.*"`; host is AMD (`k10temp`) and `chip` is a sysfs path | Selects by driver name through `node_hwmon_chip_names` |
| `HighScrapeFail` | `rate()` of `prometheus_sd_failed_configs`, a gauge that is always 0 with static configs | Now rate of rejected scraped samples; unreachable targets stay with `ServiceDown` |
| `GPUPressure` | `rate()` of a PCIe throughput sample is noise | Reduced to `DCGM_FI_DEV_GPU_UTIL > 95` |
| `FilesystemCritical` | excluded `/` despite being the root-filesystem alert | Exclusion removed |
| `GPUVRAMCritical` / `GPUVRAMWarning` | annotation said MB; DCGM reports MiB | Annotation only |

Not changed: `ServiceDown` (`up == 0`) semantics; a comment now lists the jobs
expected to be down. `NetworkInterfaceDown`'s device regex is unverified (needs
`ip -br link` on the host, and node-exporter is not on the host network
namespace). Unit tests: `configs/prometheus/tests/alerts_test.yml`.
