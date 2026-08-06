#!/bin/bash
# Project Atlas — PERMANENT tunnel setup on a REAL DOMAIN (run ONCE).
#
# Prerequisites (done by you, not this script):
#   1. The domain's nameservers point at Cloudflare (set in your registrar,
#      e.g. GoDaddy: replace NS with the two Cloudflare nameservers).
#   2. The domain is added as a zone in your Cloudflare account (Websites ->
#      Add a Site -> Free).
#
# This script then:
#   - logs cloudflared into Cloudflare (browser paste-code step, once),
#   - creates a named tunnel "atlas-portal",
#   - creates the DNS CNAME  <HOST>.<DOMAIN> -> tunnel (via `tunnel route dns`),
#   - writes ~/.cloudflared/config.yml pointing at that hostname,
#   - prints the permanent URL.
#
# Usage:
#   bash bin/setup_tunnel.sh [DOMAIN] [HOST]
#   default: DOMAIN=ilyatorchinsky.com  HOST=portal
#   -> permanent URL: https://portal.ilyatorchinsky.com
set -e
CF_BIN="/Users/it/.local/bin/cloudflared"
[ -x "$CF_BIN" ] || CF_BIN="/Users/it/Project_Atlas/bin/cloudflared"

DOMAIN="${1:-ilyatorchinsky.com}"
HOST="${2:-portal}"
FQDN="$HOST.$DOMAIN"

echo "==> Step 1: logging cloudflared into Cloudflare (browser paste-code)..."
"$CF_BIN" tunnel login

echo "==> Step 2: creating named tunnel 'atlas-portal'..."
"$CF_BIN" tunnel create atlas-portal

echo "==> Step 3: routing DNS  $FQDN -> tunnel (creates CNAME in Cloudflare)..."
"$CF_BIN" tunnel route dns atlas-portal "$FQDN"

TUNNEL_ID=$("$CF_BIN" tunnel list --output json 2>/dev/null | grep -oE '"[0-9a-f]{8}-[0-9a-f-]{27,}' | head -1 | tr -d '"')
mkdir -p "$HOME/.cloudflared"
cat > "$HOME/.cloudflared/config.yml" <<EOF
tunnel: $TUNNEL_ID
credentials-file: $HOME/.cloudflared/$TUNNEL_ID.json
ingress:
  - hostname: $FQDN
    service: http://localhost:8501
  - service: http_status:404
EOF

echo "==> Done. Permanent URL: https://$FQDN"
echo "==> start anytime with: bash /Users/it/Project_Atlas/bin/start_named_tunnel.sh"
echo "==> start_atlas.sh will auto-use this named tunnel (no URL change on reboot)."
