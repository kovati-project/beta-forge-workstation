# Runbook: serve the Authentik login over HTTPS (`auth.ai.local`)

**Config:** `configs/caddy/Caddyfile.security` (site `auth.ai.local`)  
**Tracks:** issue #50 (forward-auth works, but the login hop was plain HTTP)  
**Applies to:** the workstation host (`adapress`) and every client that opens `https://ai.local`

## Why

Caddy forward-auth sends unauthenticated requests to Authentik's authorize
endpoint. Before this change that redirect pointed at
`http://192.168.1.103:9080/application/o/authorize/...`, so the Authentik login
page, and the username and password typed into it, crossed the LAN unencrypted.

Caddy now serves Authentik on its own TLS site, `https://auth.ai.local`
(`reverse_proxy authentik:9000` over the `ai-auth` network). Authentik does not
work reliably under a sub-path, which is why this is a separate hostname and not
`https://ai.local/auth/`.

## Where the redirect URL comes from

It is **not** in the repo. Nothing in `docker/compose.auth.yml`, the deploy
scripts or a blueprint sets it, and the `authentik` container has no
`AUTHENTIK_HOST*` variable. Two settings in Authentik's database decide it:

| Setting | Where in the Authentik UI | Current value | Target |
|---|---|---|---|
| Embedded outpost `authentik_host` | Applications > Outposts > *authentik Embedded Outpost* > Edit > Advanced settings > Configuration | `http://192.168.1.103:9080` (the host of the authorize redirect; the embedded outpost fills it in from the first URL Authentik was opened on) | `https://auth.ai.local/` |
| Proxy provider external host | Applications > Providers > *(the Caddy forward-auth proxy provider)* > Edit | `https://ai.local` (visible as the `redirect_uri=https://ai.local/outpost.goauthentik.io/callback` in the redirect) | unchanged |

For the embedded outpost, `authentik_host` is only used to build the URLs sent to
the **browser**. The outpost reaches the Authentik API in-process, so the
container doesn't have to resolve `auth.ai.local` or trust Caddy's internal CA.

The forward-auth endpoints stay where they are: `/outpost.goauthentik.io/*` on
`ai.local` (including the OAuth callback), unchanged.

## Procedure

### 1. Clients: hosts entries

Add `auth.ai.local` next to `ai.local`, pointing at the workstation's LAN address
(currently `192.168.1.102`; `192.168.1.103` is the same box on `eno1`):

```text
# Linux/macOS: /etc/hosts    Windows: C:\Windows\System32\drivers\etc\hosts (as admin)
192.168.1.102  ai.local auth.ai.local
```

The certificate for `auth.ai.local` is issued by the same Caddy internal CA as
`ai.local`. A client that already trusts that root
(`/data/caddy/certs/caddy/pki/authorities/local/root.crt` on the host) trusts the
new name too. Otherwise the browser shows the same warning it shows for
`ai.local`.

### 2. Host: deploy the Caddyfile and reload Caddy

```bash
cd ~/share/src/beta-workstation      # the repo checkout on the host (see host-pull-migration.md)
git pull

# Optional: validate first, without touching the live config
docker exec -i caddy caddy validate --adapter caddyfile --config /dev/stdin \
  < configs/caddy/Caddyfile.security

# cp writes in place, so the single-file bind mount keeps working
# (don't use sed -i or an editor that replaces the file: that breaks the mount).
sudo cp configs/caddy/Caddyfile.security /data/caddy/Caddyfile
docker exec caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

Check that the new site answers before you change Authentik:

```bash
curl -sk -o /dev/null -w '%{http_code}\n' \
  --resolve auth.ai.local:443:127.0.0.1 https://auth.ai.local/-/health/live/
# expect 200 (2xx)
```

### 3. Authentik UI: point the embedded outpost at `https://auth.ai.local/`

1. Open `https://auth.ai.local/if/admin/` (the old `http://<host>:9080/if/admin/`
   still works, but then your admin password goes over HTTP again) and log in as an
   admin.
2. **Applications > Outposts**. On the row **authentik Embedded Outpost**, click
   **Edit** (pencil icon).
3. Expand **Advanced settings**. In the **Configuration** YAML, set:

   ```yaml
   authentik_host: https://auth.ai.local/
   ```

   Leave the other keys as they are. If an `authentik_host_browser` key is
   present and not empty, set it to the same value or clear it.
4. Click **Update**. The embedded outpost picks up the change within a few seconds
   (no restart needed).
5. **Applications > Providers**: open the proxy provider used by Caddy
   (forward auth) and confirm that **External host** is `https://ai.local`. Don't
   change it: the OAuth callback must go back to `ai.local`, where
   `/outpost.goauthentik.io/*` is routed.

### 4. Verify

From the host, without a session:

```bash
curl -sk -o /dev/null -D - --resolve ai.local:443:127.0.0.1 \
  https://ai.local/grafana/ | grep -iE '^(HTTP|location)'
# expect: HTTP/2 302
#         location: https://auth.ai.local/application/o/authorize/?client_id=...
#                   &redirect_uri=https%3A%2F%2Fai.local%2Foutpost.goauthentik.io%2Fcallback...
```

Then, from a client with the hosts entries, open `https://ai.local/grafana/` in a
browser. You should land on the Authentik login at `https://auth.ai.local/...`
(padlock, no `http://` anywhere in the address bar). After you log in you should
be sent back to `https://ai.local/grafana/`.

## Rollback

Set `authentik_host` back to `http://192.168.1.103:9080` on the embedded outpost
(step 3). The `auth.ai.local` Caddy site can stay; it is unused if nothing
redirects to it.

## Follow-ups (not done here)

- Authentik is still published on `:9080` (HTTP) and `:9443`. Once logins go
  through `auth.ai.local`, restrict those ports to localhost/management with UFW
  (`docs/runbooks/ufw-setup.md`, #33). Don't remove the port mapping: the deploy,
  health and validation scripts probe `http://localhost:9080`.
- The `/if/*` route on `ai.local` (initial setup without auth) is now redundant
  with `auth.ai.local` and can be removed in a later change.
