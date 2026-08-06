#!/bin/bash
# Start the STABLE named Cloudflare tunnel (atlas-portal) once it has been
# created via bin/setup_tunnel.sh. This URL never changes on reboot.
# If the named tunnel isn't set up yet, fall back to a quick tunnel and print
# its (temporary) URL so the portal is always reachable.
set -u
CF_BIN="/Users/it/.local/bin/cloudflared"
[ -x "$CF_BIN" ] || CF_BIN="/Users/it/Project_Atlas/bin/cloudflared"
CFG="$HOME/.cloudflared/config.yml"

if [ -f "$CFG" ]; then
  echo "Starting STABLE named tunnel ($(grep -oE 'hostname: [^ ]+' "$CFG" | head -1 | awk '{print $2}'))..."
  exec "$CF_BIN" tunnel run atlas-portal
else
  echo "Named tunnel not configured yet — using a temporary quick tunnel."
  echo "Run: bash bin/setup_tunnel.sh  (after the domain's DNS is on Cloudflare)"
  exec "$CF_BIN" tunnel --url http://localhost:8501 --no-autoupdate
fi
