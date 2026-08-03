# TASK-114 — Validate Caddy forward-auth protects service endpoints end-to-end

**Issue:** #50
**Result: FAIL** — forward-auth cannot be tested because **Caddy's TLS listener is
broken**. The entire proxied surface is unreachable.

## Evidence

Port 80 is alive and doing what it should — redirecting to HTTPS:

```
HTTP/1.1 301 Moved Permanently
Location: https://localhost/
Server: Caddy
```

Port 443 accepts the TCP connection and then fails the handshake:

```
curl -k https://localhost:443/   ->  HTTP code 000
openssl s_client -connect localhost:443
  error:0A000438:SSL routines:ssl3_read_bytes:tlsv1 alert internal error
  SSL alert number 80
```

TLS alert 80 is `internal_error` — the server aborting the handshake itself, not a
certificate-trust rejection on the client side (which `-k` would have suppressed
anyway).

## Why this blocks the task

Every service Caddy fronts is reached over 443. With the handshake failing, no
request ever reaches the forward-auth directive, so there is nothing to observe: no
302 to Authentik, no 401, no pass-through. The task's question — "does forward-auth
actually protect these endpoints?" — is unanswerable in this state.

It also means the practical security posture right now is that the Caddy-fronted
entry point serves nothing at all, while the individual service ports remain directly
reachable on the LAN (3000, 3001, 8800, 9091 and the rest are all listening). Whatever
protection forward-auth is meant to provide, it is not currently in the path.

## Relationship to the prior fix

`docs/authentik-caddy-debug-handoff.md` records Authentik and Caddy being
root-caused and fixed on 2026-06-29 (`authentik` missing `command: server`,
`Caddyfile.security` carrying invalid v2 directives). Those fixes addressed
crash-looping; this is a live TLS fault on a running listener, so it is a separate
condition rather than a regression of that work.

Note also #62 — `deploy-phase13.sh` never copies `Caddyfile.security` to
`/data/caddy/Caddyfile` — which means the running config may not be the hardened one
at all. That is a plausible cause worth checking first.

## Verdict

Fails, blocked. Fix the 443 handshake before this validation can proceed. Start with
#62, since a config that was never deployed is the cheapest explanation.
