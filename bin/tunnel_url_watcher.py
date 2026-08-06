#!/usr/bin/env python3
"""
ATLAS CAPITAL — tunnel URL watcher.

The portal now uses a PERMANENT named Cloudflare tunnel on
portal.ilyatorchinsky.com, so the URL never changes on reboot and no
"new link" ping is needed. This script:

  * Reads the stable URL from ~/.cloudflared/config.yml (hostname field).
  * Falls back to scanning logs/tunnel.log for a *.trycloudflare.com URL
    (in case the temporary quick tunnel is ever used).
  * Prints the current portal URL on first run, then stays silent ("OK: ...")
    on every subsequent run — the permanent URL does not change.

Run on a schedule (Hermes cron). The cron stays silent on "OK".
"""
import sys
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "logs" / "tunnel.log"
STATE = ROOT / "data" / ".tunnel_url"
NAMED_CFG = Path.home() / ".cloudflared" / "config.yml"
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def _read_named_hostname():
    if not NAMED_CFG.exists():
        return None
    text = NAMED_CFG.read_text(errors="ignore")
    m = re.search(r"hostname:\s*([^\s]+)", text)
    if m:
        return "https://" + m.group(1).strip()
    return None


def current_url():
    # Permanent named tunnel wins (stable URL)
    named = _read_named_hostname()
    if named:
        return named
    # Fallback: scan the tunnel log for a quick-tunnel URL
    if LOG.exists():
        matches = URL_RE.findall(LOG.read_text(errors="ignore"))
        if matches:
            return matches[-1]
    return None


def main():
    url = current_url()
    if not url:
        print("OK: tunnel url not yet available")
        return

    prev = ""
    if STATE.exists():
        try:
            prev = json.load(open(STATE)).get("url", "")
        except Exception:
            prev = ""

    if url == prev:
        print("OK: tunnel url stable")
        return

    STATE.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"url": url}, open(STATE, "w"))

    if prev:
        # Should essentially never happen now (permanent URL)
        print(
            "⚡ ATLAS CAPITAL — portal URL changed\n"
            f"The secure link was regenerated:\n{url}\n"
            "Re-share this with your members."
        )
    else:
        print(
            "⚡ ATLAS CAPITAL — portal is live (permanent URL)\n"
            f"Secure member link:\n{url}\n"
            "This URL is stable and survives restarts. Share with approved friends."
        )


if __name__ == "__main__":
    main()
