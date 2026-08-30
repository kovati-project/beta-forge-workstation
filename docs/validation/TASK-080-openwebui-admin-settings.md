# TASK-080 — Validate Open WebUI admin settings are configured correctly

**Issue:** #34
**Result: PASS on the stated check / FAIL on SSO integration**

## The stated check passes

`GET http://192.168.1.103:3000/api/config` (Open WebUI 0.9.6):

```
enable_signup                         False
auth                                  True
enable_login_form                     True
enable_signup_password_confirmation   False
auth_trusted_header                   False
enable_ldap                           False
enable_websocket                      True
default_models                        None
oauth.providers                       {}
```

**Signup is disabled and authentication is on**, which is what
`ENABLE_SIGNUP=false` (`docker/compose.webui.yml:41`) intends. Confirmed against the
runtime config rather than the container environment, which is stronger evidence —
`docker inspect` shows what was *passed*, this shows what is actually *in effect*.
(`docker inspect` was unavailable anyway; `nestled` is not in the `docker` group.)

## The finding the issue does not ask about

**Open WebUI is not wired into the SSO architecture at all:**

- `auth_trusted_header: False` — Open WebUI will not accept forward-auth headers, so
  even a working Caddy → Authentik chain could not sign a user in. Identity would stop
  at the proxy.
- `oauth.providers: {}` — no OAuth provider is registered, so there is no Authentik
  login path either.
- `enable_login_form: True` — the local username/password form is the only way in.

The Phase 13 design is Caddy forward-auth in front of Authentik in front of the
services. Open WebUI is configured for **neither** mechanism. Combined with #50
(Caddy's TLS listener is broken) and #33 (UFW disabled), the practical access path
today is: connect directly to port 3000 over the LAN and use a local account, with
the entire identity layer bypassed.

That local account is at least genuinely gated — signup off, auth on — so this is a
missing integration rather than an open door.

## Verdict

The task's own question passes. Flagging the SSO gap separately: it is invisible if
you only check the signup flag, and it means #50 cannot deliver SSO for this service
even once TLS is fixed.
