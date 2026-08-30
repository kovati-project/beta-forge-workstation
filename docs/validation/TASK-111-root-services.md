# TASK-111 — Verify no services are running as root unnecessarily

**Issue:** #43
**Result: FAIL (aggregate) / PARTIAL (detail)** — 20 containers flag as possibly root;
per-container attribution was not obtainable.

## Evidence

`scripts/security-hardening-audit.sh`:

```
⊘ 20 container(s) may be running as root
Privileged containers (should be documented): 0
⊘ Only 0 services have read-only root filesystem
⊘ Only 0 services drop ALL capabilities
⊘ Only 0 services have no-new-privileges
```

## What this establishes

- **No container is privileged.** That is the most dangerous category and it is clean.
- **20 containers may run as root**, i.e. no `user:` directive constrains them.
- **No container drops capabilities, sets `no-new-privileges`, or uses a read-only
  root filesystem.** So a root process inside any of them retains the full default
  capability set.

## Expected exceptions

The issue lists acceptable cases verified against the compose files — `dcgm-exporter`
(`cap_add: SYS_ADMIN` for GPU telemetry), and others needing the Docker socket or GPU
access. Those remain legitimate. The finding is that the count is 20 rather than the
handful the exceptions would justify.

## Why per-container detail is missing

The issue's command is:

```
docker ps -q | xargs -I{} docker inspect {} --format '{{.Name}}: User={{.Config.User}} ...'
```

The `nestled` account is not in the `docker` group. Beyond the permission problem,
every SSH session that issued a `docker ps` / `docker inspect` during this validation
was reset by the host mid-command — reproducibly, across several attempts, while
non-docker commands on the same session ran fine. The audit script obtains its counts
through its own path, which is why the aggregate is available and the breakdown is
not.

That SSH behaviour is worth investigating on its own; it is not a normal failure mode.

## Verdict

Fails in aggregate. To close this properly someone with docker group membership needs
to run the per-container inspect and mark each of the 20 as justified or fixable.
