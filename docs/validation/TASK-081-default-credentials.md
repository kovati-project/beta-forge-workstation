# TASK-081 — Validate all default credentials have been changed

**Issue:** #35
**Result: MIXED** — one default is confirmed changed, no hardcoded secrets remain in
compose, but the deployed host has **no `.env` file at all**.

## Confirmed changed

Grafana rejects the documented default:

```
$ curl -u admin:changeme http://localhost:3001/api/datasources
{"message":"Invalid username or password","messageId":"password-auth.failed","statusCode":401}
```

## Confirmed clean

`scripts/security-hardening-audit.sh`:

```
✓ No obvious hardcoded secrets in compose files
```

Consistent with `f486145` (MinIO password removed) and `39990e4` (SearXNG secret
rotated) — though note both of those commits are **absent from the deployed copy**
(see #44): the host is at `9ffd774`.

## The problem

```
Secrets Management:
  ⊘ No Docker secrets found
  ⊘ .env file missing (needed for Authentik POSTGRES_PASSWORD, etc)
  ⊘ .env not in .gitignore (secrets at risk!)
```

**`.env` is missing on the deployed host.** Services currently running received their
environment at start time and are unaffected, but any `docker compose up` from this
checkout will fall back to compose defaults or fail outright. `scripts/init-secrets.sh`
— which generates the strong random values the issue describes — has evidently not
been run here, or its output was not retained.

The `.env not in .gitignore` warning deserves checking against the real repo rather
than the stale deployment, since a missing file cannot leak.

## Not covered

Enumerating live credentials per service requires either `docker exec` (not available
— `nestled` is not in the `docker` group) or reading secrets, which is out of scope
for a read-only audit. Only Grafana was directly probed, because the issue named its
default explicitly.

## Verdict

Mixed. Grafana is good and compose is clean, but the missing `.env` means the secret
material on this host is not reproducible from the repo. Resolve alongside the stale
deployment in #44.
