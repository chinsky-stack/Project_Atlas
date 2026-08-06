#!/bin/bash
# Project Atlas — PERMANENT tunnel setup (run ONCE, after you create a free
# Cloudflare account).
#
# Steps this script performs (you must complete step 1 in a browser):
#   1. Create a free Cloudflare account: https://dash.cloudflare.com/sign-up
#      (no card required). You do NOT need to add any domain.
#   2. Run this script. It will open a browser to log cloudflared into your
#      account (paste the code shown).
#   3. It creates a named tunnel "atlas-portal" and writes its credentials to
#      ~/.cloudflared so it survives reboots.
#   4. Prints the stable URL.
#
# After this runs once, `start_atlas.sh` will use the named tunnel automatically
# (bin/start_named_tunnel.sh), so the URL never changes on reboot.
set -e
CF_BIN="/Users/it/.local/bin/cloudflared"
if [ ! -x "$CF_BIN" ]; then
  CF_BIN="/Users/it/Project_Atlas/bin/cloudflared"
fi

echo "==> Step 1: logging cloudflared into your Cloudflare account..."
"$CF_BIN" login

echo "==> Step 2: creating named tunnel 'atlas-portal'..."
"$CF_BIN" tunnel create atlas-portal

echo "==> Step 3: writing tunnel config..."
mkdir -p /Users/it/Project_Atlas/.cloudflared
TUNNEL_ID=$("$CF_BIN" tunnel list --output json 2>/dev/null | grep -oE '"[0-9a-f]{8}-[0-9a-f-]{27,}' | head -1 | tr -d '"')
cat > /Users/it/Project_Atlas/.cloudflared/config.yml <<EOF
tunnel: $TUNNEL_ID
credentials-file: $HOME/.cloudflared/$TUNNEL_ID.json
ingress:
  - hostname: atlas-portal.trycloudflare.com
    service: http://localhost:8501
  - service: http_status:404
EOF

echo "==> Done. Your stable tunnel id: $TUNNEL_ID"
echo "==> Start it any time with: bash /Users/it/Project_Atlas/bin/start_named_tunnel.sh"
echo "==> The URL 'atlas-portal.trycloudflare.com' will now persist across reboots."
