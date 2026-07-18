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
