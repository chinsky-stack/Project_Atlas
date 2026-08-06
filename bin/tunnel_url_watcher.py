#!/usr/bin/env python3
"""
ATLAS CAPITAL — tunnel URL watcher (self-healing quick tunnel).

The free Cloudflare quick tunnel URL changes whenever the tunnel restarts
(e.g. after a Mac/Starlink reboot). This script reads the CURRENT URL from the
tunnel log and compares it to the last-known URL stored in data/.tunnel_url.

  * If the URL is new/changed -> prints a Telegram-ready message with the new
    portal link (so Dr. King can re-share it with friends).
  * If unchanged -> prints "OK: tunnel url stable".

Run on a schedule (Hermes cron, every ~10 min). The cron stays silent on "OK".
"""
import sys
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "logs" / "tunnel.log"
STATE = ROOT / "data" / ".tunnel_url"
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def current_url():
    if not LOG.exists():
        return None
    text = LOG.read_text(errors="ignore")
    matches = URL_RE.findall(text)
    if not matches:
        return None
    # last occurrence is the most recent tunnel's URL
    return matches[-1]


def main():
    url = current_url()
    if not url:
        print("OK: tunnel url stable")  # no URL seen yet; don't nag
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

    # changed (or first run) -> persist + report
    STATE.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"url": url}, open(STATE, "w"))

    if prev:
        print(
            "⚡ ATLAS CAPITAL — portal URL changed\n"
            f"The secure link was regenerated (likely after a restart):\n"
            f"{url}\n"
            "Re-share this with your members. They sign in with their approved account."
        )
    else:
        print(
            "⚡ ATLAS CAPITAL — portal is live\n"
            f"Secure member link:\n{url}\n"
            "Share this with approved friends."
        )


if __name__ == "__main__":
    main()
