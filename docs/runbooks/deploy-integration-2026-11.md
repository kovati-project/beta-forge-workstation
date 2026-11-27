# Runbook: deploy the 2026-11 integration build to Adapress without touching vLLM

**Applies to:** `adapress`, run as `kasemo` (sudo where marked)
**Deploys:** `integration/2026-11-14` after #115, #116, #117 and #110 are merged into it
**Hard requirement:** `vllm-4gpu` and `vllm-embed` keep running throughout. No step restarts them.

## Read first

1. **Always use the `share` path for the repo:** `/home/kasemo/share/src/beta-workstation`.
   `/home/kasemo/share` is a symlink to `/srv/src`. Compose stores the resolved bind-mount
   paths in each container's config hash. `ai-inference` was started from the `share`
   path, so running compose from `/srv/src/...` changes the hash of `vllm-4gpu` and
   recreates it. From the `share` path the new build hashes identically (checked
   2026-11-26).
2. **Never run `up` without a service list.** The default services of
   `compose.training.yml` include `kohya` (GPU1+2), which is not running today. A bare
   `up -d` would start it on GPUs that `vllm-4gpu` holds. Every `up` below names its
   services and passes `--no-deps`.
3. **Do not run `up` on `compose.inference.yml` at all.** It is already identical to
   what runs. Profile changes (pair A/B, Huihui) go through the dashboard in a window
   of their own.
4. Don't use `scripts/start-all.sh`, and don't `systemctl start ai-workstation`. They
   bring up whole stacks.

Expect short interruptions while containers are recreated: about a minute for SSO (Authentik), Open WebUI, n8n,
Dify, Grafana/Prometheus and the dashboard. MinIO and Postgres restart once each.

**Scripted:** `bash scripts/deploy-integration-2026-11.sh` runs steps 1 and 4-9 with the
guards below (as kasemo; it asks for sudo for steps 1 and 9). `--dry-run` prints the
commands, and `--from <step>` resumes after a failure.

**Grafana on a pre-e50b012 volume:** step 6c used to crash-loop with `Datasource
provisioning error: data source not found`, because the volume held a "Prometheus"
datasource with a generated uid. The provisioning file now deletes and recreates it with
`uid: prometheus`. Fixed 2026-11-27.

## 0. Session setup

```bash
cd /home/kasemo/share/src/beta-workstation
REPO=$PWD
# compose with the share path as project directory and the repo .env
dcp() { local proj=$1 file=$2; shift 2
        docker compose -p "$proj" --project-directory "$REPO/docker" \
          --env-file "$REPO/docker/.env" -f "$REPO/docker/$file" "$@"; }
docker ps --format '{{.Names}} {{.Status}}' | sort > ~/pre-deploy-ps-$(date +%Y%m%d).txt
```

## 1. Back up with the current checkout

```bash
sudo bash scripts/backup.sh all          # ~10-20 min; exit 0 expected
```

The newest run directory is `/data/backups/<timestamp>/`. Don't continue on a non-zero exit.

## 2. Save the host's local state

The host's uncommitted `compose.inference.yml` edits are in the repo now (#115), so
they can be discarded. Keep a copy anyway:

```bash
git diff > ~/host-local-$(date +%Y%m%d).patch
cp docker/compose.inference.yml ~/compose.inference.yml.pre-deploy
git stash list                            # 3 old stashes; leave them
```

## 3. Switch the checkout

```bash
git checkout -- docker/compose.inference.yml loadout-manager/static/.gitkeep
git fetch origin
git switch --detach origin/integration/2026-11-14
git log --oneline -1                      # note the commit for the deploy record
```

The untracked `*.bak-*`, `package.json` and `run-script.sh` files don't block the switch.

## 4. Pre-flight check (read-only)

```bash
bash scripts/predeploy-check.sh
```

Expect:

- `vllm-4gpu` and `vllm-embed` are **not listed** (unchanged). If either shows
  `RECREATE`, **stop here**: you are not in the `share` path, or the branch is not the
  one reviewed.
- `MISMATCH` for exactly `alertmanager`, `axolotl` and `invokeai`. They live in a stray
  compose project named `docker`, left by the old in-container switch bug. Step 5 removes them.
- `RECREATE` for most other services. That's expected, because this build changes them.
- At the bottom, the `.env` keys that exist in `.env.example` but not in your `.env`.
  Each one is documented in `docker/.env.example`, and all except `AUTHENTIK_TOKEN` have
  working defaults. `AUTHENTIK_TOKEN` is only needed to assign roles from the Admin
  panel. Add any you want now. Never paste values into chat or tickets.

## 5. Remove the stray `docker`-project containers

```bash
docker rm -f alertmanager axolotl invokeai
```

`alertmanager` comes back in step 6c under `ai-monitoring`. `axolotl` has been exited for
five months. `invokeai` is behind the `studio` profile, and it shared GPU0 with
`vllm-4gpu`. Start it only when you need it.

## 6. Bring the stacks up, in this order

```bash
# a. storage: MinIO is now built from source (5-10 min the first time)
dcp ai-storage compose.storage.yml build minio
dcp ai-storage compose.storage.yml up -d --no-deps postgres qdrant minio
bash scripts/setup-minio-buckets.sh       # idempotent
python3 scripts/setup-qdrant.py           # idempotent

# b. auth (same Authentik version, 2025.2.4, so there are no migrations)
dcp ai-auth-stack compose.auth.yml up -d --no-deps postgres redis authentik authentik-worker

# c. monitoring
dcp ai-monitoring compose.monitoring.yml up -d --no-deps \
    prometheus grafana alertmanager node-exporter cadvisor dcgm-exporter

# d. voice (piper-openai is new: the OpenAI TTS adapter in front of Piper)
dcp ai-voice compose.voice.yml up -d --no-deps whisper piper piper-openai

# e. web UI (Open WebUI now stores RAG vectors in the shared Qdrant)
dcp ai-webui compose.webui.yml up -d --no-deps searxng open-webui

# f. agentic (n8n and Dify now point at vllm-4gpu by container name)
dcp ai-agentic compose.agentic.yml up -d --no-deps n8n dify-api dify-db dify-redis

# g. studio and training: only what runs today (NOT kohya)
dcp ai-studio   compose.studio.yml   up -d --no-deps comfyui rembg
dcp ai-training compose.training.yml up -d --no-deps jupyterlab label-studio

# h. caddy
dcp ai-caddy compose.caddy.yml up -d --no-deps caddy
```

After each command, `docker ps --filter name=<service>` should show the service as Up.
If one fails, check `docker logs <name> --tail 50` before going on. Every stack is
independent of vLLM.

Not started on purpose: `langfuse` (has been failing for 5 weeks, a separate issue),
`dify-web`, the MCP servers (#93 fixes them; start them with
`dcp ai-agentic compose.agentic.yml up -d --no-deps mcp-fetch mcp-filesystem mcp-browser`
when wanted), and `kohya`.

## 7. Loadout manager (UI build + image)

```bash
bash scripts/deploy-ui.sh                 # npm ci, vite build, image build, restart, health wait
curl -s localhost:8800/status | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["active_profile"], d["running_services"])'
```

Expect `inference-4gpu ['vllm-4gpu', 'vllm-embed']` only if no other profile-managed
service is running. The startup reconcile adopts a profile only on an exact match, so with
comfyui, rembg and label-studio up next to vLLM (as on Adapress, 2026-11-27) it logs
`match no profile; not adopting` and reports `None []`. That is harmless: it only reads
`docker ps`, and nothing is started or stopped.

## 8. Verify

```bash
bash scripts/predeploy-check.sh                           # exit 0; no MISMATCH; RECREATE only for
                                                          # the stopped ones (langfuse, mcp-*) and
                                                          # loadout-manager (deploy-ui.sh does not
                                                          # pass the share --project-directory)
curl -s localhost:8002/v1/models | grep -o '"id":"[^"]*"' # "id":"qwen3.8-27b"
curl -s localhost:8003/v1/models | grep -o '"id":"[^"]*"' # "id":"nomic-embed-text"
docker inspect vllm-4gpu --format '{{.State.StartedAt}}'  # unchanged: 2026-11-17T02:12:47Z
bash scripts/healthcheck.sh
```

From a Windows client: `.\scripts\test-coding-agent.ps1` (tool calls, FIM, embeddings, OpenHands).

## 9. Nightly backups

```bash
sudo bash scripts/install-backup-timer.sh     # ai-workstation-backup.timer, 03:30 nightly, as root
sudo systemctl start ai-workstation-backup.service   # one run now on the new backup.sh
journalctl -u ai-workstation-backup -n 30 --no-pager # ends with the summary; exit 0
```

Afterwards, `/data/backups/<run>` should contain mode-600 archives. If the MinIO alias is
configured (step 6a sets it), the same files are copied to `local/backups/<run>/` in MinIO.

## Rollback

vLLM is never touched, so a rollback only concerns the other stacks:

```bash
cd /home/kasemo/share/src/beta-workstation
git switch feat/ollama-coding-agent && git apply ~/host-local-YYYYMMDD.patch
# then repeat step 6 for the stacks you want back, using the old checkout
```

MinIO's data is not downgraded by the newer release. To go back to the old image, set
`image: minio/minio:latest` (still present locally) for that one `up`. Authentik's
version doesn't change. Postgres data is not migrated by this build. Restore from the
step 1 backup only if a service's data is damaged (see `scripts/backup.sh` restore hints).
