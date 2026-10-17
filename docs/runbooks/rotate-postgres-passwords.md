# Runbook: Rotate the PostgreSQL role passwords (langfuse, n8n, dify)

**Applies to:** a live workstation whose shared Postgres (`postgres` container,
`docker/compose.storage.yml`) was first initialised from a `configs/postgres/init.sql`
that was committed to this repo.

**Why this exists:** until `init.sql` became a gitignored, template-rendered file, the
three role passwords below were committed in plain text to a public repository and are
still present in git history. Treat them as compromised. Rewriting history does not
un-leak them; only rotating them on the live host does.

**From the UI:** Settings → Secrets → Rotate (`POST /api/secrets/<KEY>/rotate`) now
follows this same procedure for `POSTGRES_ADMIN_PASSWORD`, `LANGFUSE_DB_PASSWORD`,
`N8N_DB_PASSWORD`, `DIFY_DB_PASSWORD` (both instances) and `AUTHENTIK_PG_PASSWORD`:
`ALTER ROLE` first (SQL on stdin, never in argv), then `docker/.env`, then
`up -d --force-recreate` of the consumers that are running. If an `ALTER ROLE` fails,
roles already changed are put back and `docker/.env` is not touched. A database
container that was never created (e.g. `dify-db` on a host without Dify) is skipped and
reported as `not_deployed`; a stopped one blocks the rotation until it is started.
Consumers that are not running (e.g. an exited `langfuse`) are not started: start them
yourself afterwards. It does **not** take the backups in step 3 or re-render `init.sql`
(step 6); do both yourself. The steps below remain the manual path and the reference
for what the API does.

All values in this document are placeholders. Never paste a real password into a
ticket, a commit message, a chat, or a shell command line that ends up in history.

---

## 1. What is being rotated, and who uses it

| Role (in shared `postgres`) | `docker/.env` key | Consumer | Restart needed |
| --- | --- | --- | --- |
| `langfuse` | `LANGFUSE_DB_PASSWORD` | `langfuse` container, via `DATABASE_URL` in `docker/compose.storage.yml` | yes, recreate `langfuse` |
| `n8n` | `N8N_DB_PASSWORD` | nobody today (n8n runs on SQLite, `DB_TYPE=sqlite` in `docker/compose.agentic.yml`) | no |
| `dify` | `DIFY_DB_PASSWORD` | no service uses the *shared* `dify` role today; but the same value is the superuser password of the separate `dify-db` container that `dify-api` really connects to | yes, recreate `dify-api` |

Notes:

- Rotate all three, including the two that nothing consumes. Port 5432 is published by
  `docker/compose.storage.yml`, so an unused role with a leaked password is still a
  login on a reachable database.
- `dify-db` (`postgres:15-alpine`, volume `dify-db-data`, `docker/compose.agentic.yml`)
  is a **different** Postgres instance from `postgres`. `init-secrets.sh` set
  `POSTGRES_PASSWORD=${DIFY_DB_PASSWORD}` there, so it very likely holds the exposed
  value too. It needs its own `ALTER USER` (step 5).
- Out of scope here but related: `POSTGRES_ADMIN_PASSWORD` (the `admin` superuser) was
  never in `init.sql`. If you want to rotate it, it follows the same rules (step 4,
  `ALTER USER admin ...`, then update `docker/.env`).

## 2. Why editing `init.sql` does NOT change any password

The official Postgres image runs `/docker-entrypoint-initdb.d/*.sql` **only when the
data directory is empty**, i.e. the very first time the `postgres-data` volume is
initialised. On every later start the entrypoint sees an existing cluster and skips
those scripts entirely.

Consequences:

- Changing `configs/postgres/init.sql`, re-rendering it from the template,
  `docker compose restart postgres`, or `docker compose up -d --force-recreate postgres`
  changes **nothing** about the roles that already exist.
- The only in-place way to change a role password is `ALTER USER ... WITH PASSWORD`
  (this runbook).
- The only other way is destroying the volume (`docker volume rm`), which deletes every
  database in it. Do not do that to rotate a password.

`init.sql` still matters: it is what a *brand new* volume will be initialised with, so
it must be re-rendered after rotation (step 6) or a future rebuild will resurrect the
old passwords.

Related Docker behaviour that bites during rotation: `docker compose restart <svc>`
does **not** re-read `docker/.env`. Use `docker compose up -d --force-recreate <svc>`
so the container gets the new environment.

## 3. Prepare

Run on the workstation, from the repo root. Compose files use the external Docker
network `ai-workstation`.

1. Back up the environment file and the databases.

   ```bash
   umask 077
   cp docker/.env "docker/.env.bak.$(date +%Y%m%d%H%M%S)"
   docker exec postgres pg_dumpall -U admin > "/data/backups/postgres-pre-rotate-$(date +%Y%m%d%H%M%S).sql"
   ```

   The backup files contain secrets (the `.env`) or role hashes and all data (the
   dump). Keep them mode 600 and off any synced path. `docker/.env` is excluded from
   rsync; `*.bak.*` copies next to it are not guaranteed to be, so move them out of
   the repo checkout once the rotation is verified.

2. Generate three new passwords. They end up in a SQL string literal and in a
   `postgresql://` URL, so keep to `[A-Za-z0-9._~-]` and at least 16 characters
   (`scripts/init-secrets.sh` enforces this when rendering). Hex is simplest:

   ```bash
   openssl rand -hex 16     # run three times: <NEW_LANGFUSE_DB_PASSWORD>, <NEW_N8N_DB_PASSWORD>, <NEW_DIFY_DB_PASSWORD>
   ```

   Do not reuse any value from `docker/.env.bak.*`, git history, or this document.

## 4. Change the roles in the shared `postgres`

Stop the only consumer first so it does not retry with a stale password while the role
changes (a short Langfuse outage is expected):

```bash
docker compose -f docker/compose.storage.yml stop langfuse
```

Preferred: interactive `\password`, which hashes client-side so the cleartext never
appears in shell history, `ps`, or the server log.

```bash
docker exec -it postgres psql -U admin -d postgres
```

```text
\password langfuse
\password n8n
\password dify
\q
```

Scripted alternative (same effect; the statements are visible to anyone who can read
your history or the process list, so only use it from a shell with history disabled):

```sql
ALTER USER langfuse WITH PASSWORD '<NEW_LANGFUSE_DB_PASSWORD>';
ALTER USER n8n      WITH PASSWORD '<NEW_N8N_DB_PASSWORD>';
ALTER USER dify     WITH PASSWORD '<NEW_DIFY_DB_PASSWORD>';
```

Run them with `docker exec -i postgres psql -U admin -d postgres -v ON_ERROR_STOP=1`
feeding the statements on stdin from a heredoc (quoted `'SQL'` delimiter so the shell
does not expand anything).

## 5. Change the role in `dify-db` (the instance Dify really uses)

Skip only if you have confirmed `dify-db` does not hold the exposed value. Using the
`dify` superuser of that instance:

```bash
docker exec -it dify-db psql -U dify -d dify
```

```text
\password dify
\q
```

(or `ALTER USER dify WITH PASSWORD '<NEW_DIFY_DB_PASSWORD>';`). Use the same
`<NEW_DIFY_DB_PASSWORD>` as in step 4 so one `DIFY_DB_PASSWORD` in `docker/.env`
stays correct for both.

## 6. Update `docker/.env`, then re-render `init.sql`

Edit `docker/.env` (mode 600, never commit) and set the three keys to the new values:

```text
LANGFUSE_DB_PASSWORD=<NEW_LANGFUSE_DB_PASSWORD>
N8N_DB_PASSWORD=<NEW_N8N_DB_PASSWORD>
DIFY_DB_PASSWORD=<NEW_DIFY_DB_PASSWORD>
```

`N8N_DB_PASSWORD` may not exist yet in an older `docker/.env`; add the line.

Re-render the (gitignored) init script from the tracked template so a future fresh
volume is created with the new values. `--force` is required because the existing
file holds the old passwords:

```bash
bash scripts/init-secrets.sh --render-postgres-init --force
```

This writes `configs/postgres/init.sql` mode 600. It does not touch the running
database (see section 2).

Mode note: the file is rendered mode 600. The postgres image reads it as its own
in-container user, which cannot open a 600 file owned by the host user, so on a
**fresh** volume `scripts/deploy-phase09.sh` opens it to 644 just for the first
initialisation and then restores 600. If you ever rebuild the volume by another route
(plain `docker compose up`), run `chmod 644 configs/postgres/init.sql` first or you
will see `Permission denied` in `docker logs postgres` and the roles will not be
created. On the existing volume this does not matter, because init scripts are not
read again.

## 7. Restart the consumers (recreate, not restart)

```bash
# Langfuse picks up DATABASE_URL with the new password
docker compose -f docker/compose.storage.yml up -d --force-recreate langfuse

# Dify API picks up DB_PASSWORD; dify-db may also be recreated because its env
# changed, which is harmless (the data volume and the role password persist)
docker compose -f docker/compose.agentic.yml up -d --force-recreate dify-api
```

Order: roles are already changed (steps 4 and 5) before any container is recreated, so
there is no window where a service starts with a password the database rejects.

## 8. Verify

1. **Old password is rejected.** Do not test with `docker exec postgres psql -h localhost`
   or `-h 127.0.0.1`: the image's `pg_hba.conf` uses `trust` for connections from inside
   the container, so that succeeds with any password and proves nothing. Connect from
   a separate container over the network, which hits the password-checked rule:

   ```bash
   read -rsp 'password to test: ' PGPASSWORD; export PGPASSWORD; echo
   docker run --rm --network ai-workstation -e PGPASSWORD postgres:16-alpine \
     psql -h postgres -U langfuse -d langfuse -c 'select 1'
   unset PGPASSWORD
   ```

   Expected: the **old** value fails with `password authentication failed for user
   "langfuse"`; the **new** value returns one row. Repeat for `n8n` (database `n8n`) and
   `dify` (database `dify`). For the Dify instance used by the API, use host `dify-db`.

2. **Services are healthy on the new credentials.**

   ```bash
   curl -sf http://localhost:3002/api/health && echo langfuse ok
   docker logs --since 10m langfuse 2>&1 | grep -iE 'password|auth(entication)? failed' || echo "no auth errors"
   docker logs --since 10m dify-api 2>&1 | grep -iE 'password|auth(entication)? failed' || echo "no auth errors"
   ```

   If Langfuse is published on a different port on your host (see the validation notes
   on `NEXTAUTH_URL`), adjust the port; the health path is the same.

3. **The repo no longer carries the secret.**

   ```bash
   git ls-files configs/postgres        # expect only init.sql.template
   git check-ignore -v configs/postgres/init.sql
   ```

## 9. Rollback

If Langfuse or Dify will not start after step 7:

1. Do not change the database again until you know which side is wrong. Compare the
   value Langfuse was started with against the role: `docker inspect langfuse` shows
   its environment (treat the output as secret).
2. The quickest consistent state is to set the role back to what `docker/.env` says:
   `\password langfuse` (and likewise for the others) using the value now in
   `docker/.env`, then recreate the service.
3. If `docker/.env` itself is wrong, restore from the `docker/.env.bak.*` taken in
   step 3 and repeat from step 4. The old values are compromised, so this is a
   stop-gap, not a resting state.

## 10. Afterwards

- Delete the `docker/.env.bak.*` copies and the pre-rotation dump once verified, or
  move them to your normal encrypted backup location.
- The old values remain in git history of the public repository and in any clone or
  fork made before the history was cleaned. Rotation on the host is what neutralises
  them; assume they are known to third parties.
- Record the rotation date wherever you track credentials. Do not record the values.
