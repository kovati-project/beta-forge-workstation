# mcp-code-exec: minimal sandboxed Python runner, streamable HTTP on :3102/mcp.
# See server.py for the isolation layers. Debian's python3-seccomp (libseccomp
# bindings) builds the per-run syscall filter, so the system python is used.
FROM debian:bookworm-slim

ARG MCP_VERSION=1.30.0

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv python3-seccomp tini \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/mcp \
 && /opt/mcp/bin/pip install --no-cache-dir "mcp==${MCP_VERSION}" \
 && useradd --uid 10001 --no-create-home --home-dir /tmp --shell /usr/sbin/nologin mcp

COPY server.py sandbox.py /opt/code-exec/

USER mcp
WORKDIR /tmp
EXPOSE 3102

ENTRYPOINT ["/usr/bin/tini", "--", "/opt/mcp/bin/python", "/opt/code-exec/server.py"]
