# TASK-063 — Validate Langfuse is connected to Postgres and accessible

**Issue:** #31
**Result: PARTIAL / FAIL on configuration** — Langfuse is running and reachable, but
**not on the port it is configured to advertise**.

## Evidence

| Port | Result |
| --- | --- |
| 3002 (expected) | connection refused — nothing listening |
| 3003 | HTTP 200 |

The listening-port sweep confirms 3003 is open and 3002 is not.

Postgres is up on 5432.

## The configuration defect

`docker/compose.storage.yml:65` hardcodes:

```
NEXTAUTH_URL=http://10.10.10.2:3002
```

Two faults in one line:

1. **Wrong host** — `10.10.10.2` is not an address this machine holds (see #28/#32);
   the workstation is 192.168.1.102/.103.
2. **Wrong port** — the service is actually served on 3003, not 3002.

`NEXTAUTH_URL` is what NextAuth uses to build callback URLs, so sign-in redirects
will be sent to an unreachable host on a closed port. Anyone who reaches the UI on
3003 directly will still fail at the auth round trip.

## Not covered

Confirming the Postgres *connection* from inside the container needs
`docker logs` / `docker exec`, and the `nestled` account is not in the `docker`
group. Account creation is a write and out of remit. Both deferred.

## Verdict

Reachability passes on 3003; configuration fails. Fix `NEXTAUTH_URL` to a resolvable
host and the correct port as part of #51.

## Resolution

**Correction to the findings above: Langfuse is not on 3003.** The compose files
publish Langfuse on host port **3002** (`docker/compose.storage.yml`,
`"3002:3000"`, container-internal port 3000). Port **3003** is published by
OpenHands (`docker/compose.codegen.yml`, `"3003:3000"`). No other
`docker/compose.*.yml` maps 3002 or 3003, so there is no port conflict, and the
README and `plan/PROJECT_PLAN.md` port tables agree (Langfuse 3002, OpenHands 3003).
The HTTP 200 on 3003 was therefore almost certainly OpenHands. "3002 refused" most
likely means the Langfuse container was not running at validation time, not that
it had moved to another port. The "Langfuse is running and reachable" verdict is
unsupported by the evidence.

**Fix (issue #31):** `NEXTAUTH_URL` in `docker/compose.storage.yml` is now
`${LANGFUSE_URL:-http://localhost:3002}` instead of the hardcoded, unroutable
`http://10.10.10.2:3002`. The port was already correct; the host was the defect.
`LANGFUSE_URL` is documented (commented out) in `docker/.env.example`. The
`10.10.10.2` references elsewhere in the repo are out of scope (#51).

**Still open (needs live host):** why the Langfuse container was not listening on
3002 (`docker ps -a`, `docker logs langfuse`) and the Postgres connection check
deferred under "Not covered".
