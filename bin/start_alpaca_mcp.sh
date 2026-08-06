#!/bin/bash
# Launch the Alpaca MCP server (stdio) using the SAME paper credentials as Atlas.
# It exposes Alpaca Market Data + Trading/Broker API as MCP tools for any
# MCP client (Claude Desktop, Cursor, etc.). Runs in the background; talks over
# stdin/stdout (stdio MCP transport).
set -u
MCP_DIR="/Users/it/Project_Atlas/.alpaca_mcp"
ENV_FILE="/Users/it/Project_Atlas/.env.alpaca_mcp"

# Install once if missing
if [ ! -x "$MCP_DIR/node_modules/.bin/alpaca-mcp" ]; then
  mkdir -p "$MCP_DIR"
  ( cd "$MCP_DIR" && npm install alpaca-mcp >/tmp/alpaca_mcp_install.log 2>&1 )
fi

cd "$MCP_DIR"
# Load creds into env
set -a
[ -f "$ENV_FILE" ] && . "$ENV_FILE"
set +a

exec node node_modules/alpaca-mcp/dist/index.js
