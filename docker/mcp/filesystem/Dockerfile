# mcp-filesystem: the official MCP filesystem server (stdio only) behind
# mcp-proxy, which serves it as streamable HTTP on :3100/mcp (and legacy SSE
# on /sse). The server only sees the directories passed on the command line.
FROM node:24-alpine

ARG SERVER_FILESYSTEM_VERSION=2.1.0
ARG MCP_PROXY_VERSION=0.14.0

RUN apk add --no-cache python3 tini \
 && python3 -m venv /opt/mcp-proxy \
 && /opt/mcp-proxy/bin/pip install --no-cache-dir "mcp-proxy==${MCP_PROXY_VERSION}" \
 && npm install -g --omit=dev "@modelcontextprotocol/server-filesystem@${SERVER_FILESYSTEM_VERSION}" \
 && npm cache clean --force

USER node
WORKDIR /home/node
EXPOSE 3100

ENTRYPOINT ["/sbin/tini", "--", "/opt/mcp-proxy/bin/mcp-proxy"]
CMD ["--host", "0.0.0.0", "--port", "3100", "--", "mcp-server-filesystem", "/data"]
