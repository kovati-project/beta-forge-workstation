# TASK-062 — Validate Grafana dashboards and datasource

**Issue:** #30
**Result: PARTIAL** — Grafana is healthy; datasource and dashboard checks are blocked
on credentials.

## Verified

`GET http://localhost:3001/api/health`:

```json
{"database": "ok", "version": "13.0.2", "commit": "3fcdbc5a"}
```

Grafana is up, and its own database backend is healthy.

## Blocked

The issue's step 1 says to log in with `admin/changeme`. That credential is
**rejected**:

```json
{"message":"Invalid username or password","messageId":"password-auth.failed","statusCode":401}
```

This is good news for #35 — the default password has been changed — but it means the
datasource list, the Prometheus datasource health, and the DCGM/Node-Exporter
dashboards cannot be enumerated without the current credential.

## Note

Even once credentials are supplied, the Prometheus datasource will show incomplete
data: 7 of 11 scrape targets are down because they point at `10.10.10.2` (see #28).
Dashboards will render, but GPU and inference panels will be empty for those targets.

`GF_SERVER_ROOT_URL` (`docker/compose.monitoring.yml`) carries the same `10.10.10.2`
problem flagged in #51.

## Verdict

Reachability and backend health pass. Re-run with a working credential to finish the
datasource and dashboard half.
