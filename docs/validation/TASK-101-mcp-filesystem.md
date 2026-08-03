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
