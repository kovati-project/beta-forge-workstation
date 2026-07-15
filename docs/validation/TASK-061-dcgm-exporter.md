# TASK-061 — Validate DCGM exporter image compatibility with Ubuntu 26

**Issue:** #29
**Result: PASS** — the exporter runs and produces real GPU metrics.

## Evidence

`GET http://localhost:9400/metrics` returns HTTP 200 and **76** `DCGM_FI_DEV_*`
series. Port 9400 is listening on the host.

The compatibility concern in the original issue was that the pinned image
(`nvcr.io/nvidia/k8s/dcgm-exporter:...-ubuntu22.04`, `docker/compose.monitoring.yml:53`)
might not work on an Ubuntu 26 host. It does — the container image's own userspace
is independent of the host's, and it is talking to the driver successfully.

## Caveat

Prometheus is not currently scraping this exporter usefully; see #28. The exporter
is healthy, but its metrics are not reaching dashboards while the scrape config
points at an unroutable address.

## Verdict

Passes. No image change needed.
