# mcp-fetch: the official MCP fetch server (Python, stdio only) behind
# mcp-proxy, which serves it as streamable HTTP on :3103/mcp (and legacy SSE
# on /sse). Same bridge as mcp-filesystem. Separate venvs: the two pin
# different major versions of the mcp SDK.
FROM python:3.12-slim

ARG MCP_SERVER_FETCH_VERSION=2026.10.28
ARG MCP_PROXY_VERSION=0.14.0

RUN apt-get update \
 && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/* \
 && python -m venv /opt/mcp-proxy \
 && /opt/mcp-proxy/bin/pip install --no-cache-dir "mcp-proxy==${MCP_PROXY_VERSION}" \
 && python -m venv /opt/fetch \
 && /opt/fetch/bin/pip install --no-cache-dir "mcp-server-fetch==${MCP_SERVER_FETCH_VERSION}" \
 && useradd --uid 10001 --create-home --shell /usr/sbin/nologin mcp

USER mcp
WORKDIR /home/mcp
EXPOSE 3103

ENTRYPOINT ["/usr/bin/tini", "--", "/opt/mcp-proxy/bin/mcp-proxy"]
CMD ["--host", "0.0.0.0", "--port", "3103", "--", "/opt/fetch/bin/mcp-server-fetch"]
