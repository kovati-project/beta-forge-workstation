# Host migration: untracked SearXNG settings + UI build output

One-time steps for a host whose checkout predates this change. After it, `git pull`
on the host is a plain fast-forward again.

## What changed

| Path | Before | Now |
| --- | --- | --- |
| `configs/searxng/settings.yml` | tracked, holds a real `secret_key` | **untracked**; rendered from `settings.yml.template` by `scripts/init-secrets.sh --render-searxng` |
| `loadout-manager/static/` | tracked build output | **untracked** (only `.gitkeep`); built on the host by `bash scripts/deploy-ui.sh` |
| `docker/compose.loadout.yml` | state file lost on container recreate | mounts `/data/loadout-manager` |

Why the pull used to abort: the host modified both paths in place (the SearXNG key,
the UI build), and `configs/searxng` is owned by the container user (uid 977) while
`static/assets` was created by a root-run build, so git could neither stash nor
overwrite them.

## Steps (run on the host as the normal user, with bash)

```bash
cd ~/share/src/beta-workstation

# 1. keep the host's private SearXNG key (mode 600, outside the repo)
cp -p configs/searxng/settings.yml ~/settings.yml.host-backup
chmod 600 ~/settings.yml.host-backup

# 2. let git touch the two paths for this one pull
sudo chown -R "$USER":"$(id -gn)" configs/searxng loadout-manager/static

# 3. drop local edits to tracked files that this change replaces
git checkout -- configs/searxng/settings.yml loadout-manager/static docker/compose.loadout.yml

# 4. pull (this removes the old tracked settings.yml and static bundle from disk)
git pull

# 5. restore the host's key, then hand the directory back to the container user
cp ~/settings.yml.host-backup configs/searxng/settings.yml
sudo chown -R 977:977 configs/searxng

# 6. state directory for the loadout manager, then rebuild UI + container (no sudo)
sudo mkdir -p /data/loadout-manager
bash scripts/deploy-ui.sh

# 7. restart SearXNG so it re-reads settings.yml
docker restart searxng
```

Expect the UI to return 404 between step 4 and the end of step 6 (the build output is
served straight from the checkout).

## Verify

```bash
git status --short                      # no M/D entries for settings.yml or static/
git diff --stat                         # empty
ls -l configs/searxng/settings.yml      # owned by 977, mode 664
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/    # SearXNG answers
curl -s localhost:8800/ | grep -o 'assets/index-[A-Za-z0-9_-]*\.js'   # exists in static/assets
```

## Afterwards

- **Never run these scripts with `sh`.** They now stop with a clear message; use
  `bash scripts/<name>.sh`.
- **Never build the UI or run `init-secrets.sh` with `sudo`** from this checkout; that
  is what created the root-owned files in the first place.
- **Rotating the key later:** `bash scripts/init-secrets.sh --render-searxng --force`
  (needs write access to `configs/searxng`; re-`chown` to 977 afterwards), then
  `docker restart searxng`.
- **If the old key was ever committed** (it was, in history before `39990e4`), treat
  any key that matches a committed value as public and rotate it.
