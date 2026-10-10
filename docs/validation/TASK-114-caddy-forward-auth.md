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

## Resolution

**Root cause (reproduced):** SNI mismatch, not a missing or undeployed config. The
`301 ... Location: https://localhost/` in the evidence is the `permanent` redirect
from the `:80` block of `Caddyfile.security`, so the hardened config *was* the one
running (this also rules out #62 as the cause of the handshake failure). That
config declared a single TLS site, `ai.local` with `tls internal`, so Caddy held a
certificate for that name only. A client connecting to `localhost` (as the
validation did) or to a bare IP asks for a name Caddy has no certificate for, and
Caddy aborts the handshake with TLS alert 80 `internal_error`.

Reproduced with `caddy:2-alpine` running the pre-fix Caddyfile: the cert for
`ai.local` was issued normally and `https://ai.local/.health` returned 200, while
`https://localhost/` and `https://127.0.0.1/` failed with
`error:0A000438:SSL routines::tlsv1 alert internal error` -- the same error
signature as the evidence.

**Fix (`configs/caddy/Caddyfile.security`):**

- Site address is now `ai.local, localhost`, so the name the validation probes use
  gets an internal-CA certificate and the full forward-auth route set.
- Global `default_sni ai.local` and `fallback_sni ai.local`, so SNI-less (IP) and
  unknown-SNI connections complete the handshake instead of aborting.
- New `https://` catch-all that answers `404`, so a Host header that matches no
  site is refused explicitly instead of getting Caddy's default empty `200`.

Post-fix results in the same harness: `https://localhost/.health` 200,
`https://ai.local/` 302 to `/webui`, `https://127.0.0.1/` and unknown names 404,
and a protected path was not served unauthenticated (502 there because Authentik
was not reachable in the harness, i.e. forward-auth fails closed).
`http://localhost/` now answers `308` (automatic HTTPS redirect) rather than `301`;
the `:80` block remains for other hostnames.

`scripts/deploy-phase13.sh` now also deploys the Caddyfile (#62) and starts
`compose.caddy.yml`, so a clean host gets the hardened config without a manual `cp`.

**Not verified (host state, not visible from the repo):** the live workstation's
Caddy version and the writability of `/data/caddy/certs`; and the real 302-to-
Authentik behaviour, since no Authentik was behind Caddy in the harness. Re-run this
task on the host after `bash scripts/deploy-phase13.sh`. If the handshake still
fails, in order of likelihood: (1) the running container still holds the old config
(`docker restart caddy`); (2) `/data/caddy/certs` is not writable by the container,
so issuance fails (look for `tls.obtain` errors in `docker logs caddy`); (3) clients
use a hostname not in the site address list (add it to the Caddyfile).
