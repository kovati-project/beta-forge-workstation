# TASK-070 — Audit hardcoded 10.10.10.2 references and document actual topology

**Issue:** #32
**Result: COMPLETE** — audit done. The scope is roughly 2.5x what the issue estimated.

## Actual network topology

`hostname -I` on `adapress`:

```
169.254.3.1  192.168.1.103  192.168.1.102
172.21.0.1  172.22.0.1  172.20.0.1  172.17.0.1  172.18.0.1  172.19.0.1
```

| Address | Role |
| --- | --- |
| `192.168.1.102` | LAN — SSH |
| `192.168.1.103` | LAN — HTTP services (loadout-manager :8800 etc.) |
| `172.17-22.0.1` | Docker bridge gateways |
| `169.254.3.1` | link-local, not routable |

**There is no `10.10.10.0/24` interface on this machine.** Every reference to
`10.10.10.2` is unreachable, which is the direct cause of the 7 dead Prometheus
targets (#28) and the broken Langfuse `NEXTAUTH_URL` (#31).

## Count correction

The issue estimated "50 times across 11 files" from `docker/ configs/`. Measured:

| Scope | Occurrences | Files |
| --- | --- | --- |
| `docker/` + `configs/` | 48 | 11 |
| `scripts/` | 79 | 27 |
| **Total** | **127** | **38** |

The original figure was close for the scope it measured, but it excluded `scripts/`,
which holds roughly 62% of the real total. Anyone scoping #51 from the issue text
alone would size the work at under half of what it is.

Heaviest files: `configs/caddy/Caddyfile.security` (11), `scripts/README.md` (7),
`configs/prometheus/prometheus.yml` (7), `scripts/deploy-phase10.sh` (6),
`scripts/deploy-all.sh` (6), `docker/compose.webui.yml` (6),
`docker/compose.agentic.yml` (6), `configs/continue/config.json` (6).

## A second address the issue does not mention

Two distinct addresses are hardcoded, not one:

- `10.10.10.2` — 126 occurrences
- `10.10.10.1` — 3 occurrences

Any find-and-replace scoped only to `.2` will leave three references behind.

## Verdict

Audit complete. Feeds #51 with a corrected scope: 127 occurrences, 38 files, two
distinct addresses.
