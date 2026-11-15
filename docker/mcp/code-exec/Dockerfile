# mcp-code-exec: minimal sandboxed Python runner, streamable HTTP on :3102/mcp.
# launcher.py is PID 1 (uid 0, only CAP_SETUID/CAP_SETGID from compose); it runs
# server.py as uid 10001 and each snippet as uid 10002. See server.py for the
# isolation layers. Debian's python3-seccomp (libseccomp bindings) builds the
# per-run syscall filter, so the system python runs the snippets.
FROM debian:bookworm-slim

ARG MCP_VERSION=1.30.0

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv python3-seccomp \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/mcp \
 && /opt/mcp/bin/pip install --no-cache-dir "mcp==${MCP_VERSION}" \
 && useradd --uid 10001 --no-create-home --home-dir /tmp --shell /usr/sbin/nologin mcp \
 && useradd --uid 10002 --no-create-home --home-dir /scratch --shell /usr/sbin/nologin sandbox \
 && mkdir -m 0700 /scratch && chown sandbox:sandbox /scratch

COPY launcher.py server.py sandbox.py /opt/code-exec/

# Starts as root on purpose: the launcher needs CAP_SETUID/CAP_SETGID to start
# the server and the snippets under their own uids. Compose drops every other
# capability, and no process keeps any after its setuid().
USER root
WORKDIR /
EXPOSE 3102

ENTRYPOINT ["/usr/bin/python3", "-I", "/opt/code-exec/launcher.py"]
