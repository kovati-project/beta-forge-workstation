# TASK-110 — Run Docker Bench Security and document findings

**Issue:** #42
**Result: RAN** — 2 automated checks pass, 12 flag warnings.

## Correction confirmed

The issue's correction is accurate: this repo does not use a generic
`docker/docker-bench-security` container. The checked-in tool is
`scripts/security-hardening-audit.sh`. It was run from the deployed copy at
`/srv/src/src/beta-workstation` (the issue's `~/ai-workstation` path does not exist —
see #44).

## Automated results

**Docker security — 2 passed, 0 failed, 5 warnings:**

| Check | Result |
| --- | --- |
| Containers running as root | ⊘ **20 containers may be running as root** |
| Privileged containers | 0 — good |
| Read-only root filesystem | ⊘ 0 services |
| Hardcoded secrets in compose | ✓ none found |
| Volume permissions | ✓ 0 excessive RW mounts |
| Capabilities dropped (ALL) | ⊘ 0 services |
| `no-new-privileges` | ⊘ 0 services |

**Network segmentation — 1 of 6 networks exists:**

`ai-auth` ✓. Missing: `ai-inference`, `ai-training`, `ai-storage`, `ai-monitoring`,
`ai-agents`. The segmentation model in the Ph13 spec is essentially not deployed —
five of six planned networks were never created, so services that were meant to be
isolated from each other are sharing whatever network they landed on.

**Secrets — all three warn:** no Docker secrets, `.env` missing, `.env` not
gitignored. See #35.

**Host firewall — both warn:** UFW not enabled, SSH password auth still enabled.
See #33.

**Authentik — all four pass:** service, PostgreSQL, Redis and the API on :9080 are
all running and responding.

## Reading the results

The privileged-container count of 0 is genuinely good, and Authentik being fully up
is a real positive. Everything else in the Docker section reflects hardening that was
specified but never applied — no capability drops, no `no-new-privileges`, no
read-only root filesystems anywhere across 20 containers.

Combined with UFW being off (#33) and Caddy's TLS being broken (#50), the practical
posture is: no host firewall, no working reverse-proxy gate, minimal container
hardening, and five of six network segments absent.

## Not covered

The script prints a manual checklist after the automated section — BMC hardening,
secrets rotation, forward-auth testing, audit logging, compliance review. Those are
human tasks and were not attempted. Per-container root detail needs `docker inspect`;
see #43.

## Verdict

Ran successfully. The estate is materially less hardened than the Phase 13 spec
describes. Firewall (#33) first, then network segmentation.
