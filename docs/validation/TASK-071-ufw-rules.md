# TASK-071 — Validate UFW rules are in place and correctly scoped

**Issue:** #33
**Result: FAIL** — UFW is **not enabled**. There are no rules to scope.

## Evidence

Direct check as `nestled`:

```
$ ufw status verbose
ERROR: You need to be root to run this script
```

`scripts/security-hardening-audit.sh`, which does have the necessary access,
reports plainly:

```
Host Firewall & BMC:
  ⊘ UFW firewall not enabled (sudo ufw enable)
  ⊘ SSH password auth still enabled (consider disabling)
```

## What this means

The Ph13 spec expects incoming `deny` by default with service ports reachable only
from the jumpbox. Neither half is in effect: with UFW disabled there is no default
policy and no per-port scoping, so **every listening port is reachable from anything
that can route to this host**.

That is a wide surface. The host is listening on:

```
22 53 80 443 3000 3001 3003 5000 5201 5432 5678 6333 6334 8000 8080 8081
8188 8190 8800 8888 8989 9000 9001 9080 9090 9091 9093 9099 9100 9400 9443 11434
```

Unauthenticated or weakly-authenticated services in that list include Prometheus
(9091), the loadout-manager API (8800), Qdrant (6333/6334), Ollama (11434) and
Postgres (5432).

This compounds #50: Caddy's TLS listener is broken, so the reverse proxy that was
meant to be the single guarded entry point serves nothing, while all the individual
service ports remain directly reachable. The intended architecture has forward-auth
in front; the actual posture has no gate at either layer.

Also flagged: **SSH password authentication is still enabled**, so the host accepts
password logins alongside keys.

## Not covered

Enabling UFW or adding rules is a state change on a read-only box, and getting the
scoping wrong would sever access to a machine reachable only over the LAN. Not
attempted.

## Verdict

Fails. This is the most exposed finding in the set — recommend prioritising it over
the cosmetic UI issues.
