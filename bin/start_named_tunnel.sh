#!/bin/bash
# Start the STABLE named Cloudflare tunnel (atlas-portal) once it has been
# created via bin/setup_tunnel.sh. This URL never changes on reboot.
# If the named tunnel isn't set up yet, fall back to a quick tunnel and print
# its (temporary) URL so the portal is always reachable.
set -u
CF_BIN="/Users/it/.local/bin/cloudflared"
[ -x "$CF_BIN" ] || CF_BIN="/Users/it/Project_Atlas/bin/cloudflared"
CFG="/Users/it/Project_Atlas/.cloudflared/config.yml"

if [ -f "$CFG" ]; then
  echo "Starting STABLE named tunnel (atlas-portal)..."
  exec "$CF_BIN" tunnel run atlas-portal
else
  echo "Named tunnel not configured yet — using a temporary quick tunnel."
  echo "Run bin/setup_tunnel.sh once (after creating a free Cloudflare account) for a permanent URL."
  exec "$CF_BIN" tunnel --url http://localhost:8501 --no-autoupdate
fi
