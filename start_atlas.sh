#!/bin/bash
# Project Atlas — one-click launcher for Dr. King
# Starts the Streamlit dashboard + a secure Cloudflare tunnel, with auto-restart.
# Usage:  bash start_atlas.sh
set -u

ATLAS_DIR="/Users/it/Project_Atlas"
VENV="$ATLAS_DIR/.venv/bin/activate"
CF_BIN="$ATLAS_DIR/bin/cloudflared"
if [ ! -x "$CF_BIN" ]; then
  CF_BIN="/Users/it/.local/bin/cloudflared"
fi
PORT=8501
LOG_DIR="$ATLAS_DIR/logs"
mkdir -p "$LOG_DIR"

cd "$ATLAS_DIR" || { echo "ERROR: $ATLAS_DIR not found"; exit 1; }

# Passphrase for the shared URL (override with: ATLAS_PASSWORD=xxx bash start_atlas.sh)
export ATLAS_PASSWORD="${ATLAS_PASSWORD:-atlas2026}"

echo "=============================================="
echo "  Project Atlas — starting..."
echo "  Dashboard : http://localhost:$PORT"
echo "  Passphrase: ${ATLAS_PASSWORD}"
echo "=============================================="

# ---- Streamlit (auto-restart loop) ----
run_streamlit() {
  while true; do
    echo "[$(date)] starting streamlit"
    source "$VENV"
    streamlit run main.py --server.headless true --server.port $PORT \
      >> "$LOG_DIR/streamlit.log" 2>&1
    echo "[$(date)] streamlit exited ($?), restarting in 3s"
    sleep 3
  done
}

# ---- Cloudflare tunnel (auto-restart loop) ----
# Prefer the STABLE named tunnel if it has been set up (bin/setup_tunnel.sh);
# otherwise fall back to a temporary quick tunnel whose URL changes on reboot.
# A --logfile is used so bin/tunnel_url_watcher.py can read the current URL.
NAMED_CFG="$ATLAS_DIR/.cloudflared/config.yml"
TUNNEL_LOG="$LOG_DIR/tunnel.log"
run_tunnel() {
  while true; do
    if [ -f "$NAMED_CFG" ]; then
      echo "[$(date)] starting STABLE named tunnel (atlas-portal)"
      "$CF_BIN" tunnel run atlas-portal --logfile "$TUNNEL_LOG" --loglevel info >> "$LOG_DIR/tunnel.out" 2>&1
    else
      echo "[$(date)] starting temporary quick tunnel (run bin/setup_tunnel.sh for a permanent URL)"
      "$CF_BIN" tunnel --url "http://localhost:$PORT" --no-autoupdate --logfile "$TUNNEL_LOG" --loglevel info >> "$LOG_DIR/tunnel.out" 2>&1
    fi
    echo "[$(date)] tunnel exited ($?), restarting in 3s"
    sleep 3
  done
}

# Start both in background, report the URL once the tunnel is up
run_streamlit &
run_tunnel &

# Poll the tunnel log for the public URL and print it
( for i in $(seq 1 30); do
    url=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" "$LOG_DIR/tunnel.log" 2>/dev/null | head -1)
    if [ -n "$url" ]; then
      echo ""
      echo "=============================================="
      echo "  REMOTE URL (share with friends):"
      echo "    $url"
      echo "  Passphrase: ${ATLAS_PASSWORD}"
      echo "=============================================="
      break
    fi
    sleep 2
  done ) &

wait
