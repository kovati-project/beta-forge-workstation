# TASK-101 — Validate MCP filesystem server is accessible and sandboxed correctly

**Issue:** #40
**Result: FAIL** — the MCP filesystem server is not running.

## Evidence

`docker/compose.agentic.yml:81-91` defines `mcp-filesystem` (image `node:20-alpine`)
running `npx @modelcontextprotocol/server-filesystem --port 3100 /data`.

| Check | Result |
| --- | --- |
| Port 3100 in host listening set | **absent** |
| `curl http://localhost:3100/` | HTTP code `000` |

The full listening-port sweep of the host does not include 3100:

```
22 53 80 443 3000 3001 3003 5000 5201 5432 5678 6333 6334 8000 8080 8081
8188 8190 8800 8888 8989 9000 9001 9080 9090 9091 9093 9099 9100 9400 9443 11434
```

No other MCP port (3101-3103 for browser / code-exec / fetch) is present either,
which is consistent with the whole agentic MCP stack being down rather than this one
service failing.

## Sandboxing — cannot be confirmed, but the config is worth noting

The task's second half asks whether `/data` is correctly mounted read-only.
`compose.agentic.yml:81-91` mounts `/data:/data:ro`, which is the right shape. The
issue's own note is accurate: there is no separate `/home/user` mount, so the
sandbox root is `/data` alone.

Confirming the mount as *running* requires `docker inspect`, and the `nestled`
account is not in the `docker` group. Deferred rather than assumed.

## Verdict

Fails at accessibility. The declared configuration looks correct; the service simply
is not up. Start the agentic stack, then re-run for the sandbox half.

## Fix (fix/mcp-servers) and re-run steps

Root cause, from `docker logs mcp-filesystem` on the host: the server is
stdio-only and has no `--port` flag, so it treated `--port` and `3100` as
directories, printed `Secure MCP Filesystem Server running on stdio`, saw EOF on
stdin and exited 0. Nothing ever listened on 3100.

The service is now `@modelcontextprotocol/server-filesystem` (pinned, built
from `docker/mcp/filesystem/`) behind `mcp-proxy`, serving MCP streamable HTTP
at `http://<host>:3100/mcp`.

Sandbox shape, changed deliberately: the sandbox root is still `/data` inside
the container and read-only, but only user content is mounted into it
(`/data/documents`, `/data/datasets`, `/data/outputs`, `/data/notebooks`, each
`:ro`). The host's `/data` also holds service state (authentik, n8n, caddy,
minio, backups), which an LLM-facing file server must not be able to read.
Container: uid 1000, read-only rootfs, `cap_drop: [ALL]`, `no-new-privileges`.

Re-run on the host after deploying:

```bash
bash scripts/validate-phase08.sh          # initialize handshake on :3100-3103/mcp
docker inspect mcp-filesystem --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} rw={{.RW}}{{"\n"}}{{end}}'
curl -s http://localhost:8800/api/mcp/servers | jq '.summary'
```

Then, from any MCP client pointed at `http://10.10.10.2:3100/mcp` (or Open WebUI
→ Admin Settings → External Tools → MCP (Streamable HTTP) →
`http://mcp-filesystem:3100/mcp`): `list_allowed_directories` returns `/data`,
`list_directory /data` shows the four mounts, `read_text_file /etc/passwd` and
`/data/../etc/passwd` are refused (`Access denied - path outside allowed
directories`), and `write_file` under `/data` fails with `EROFS`.
