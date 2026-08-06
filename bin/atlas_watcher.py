#!/usr/bin/env python3
"""
ATLAS CAPITAL — access watcher.

Run on a schedule (Hermes cron). Checks data/access.json for NEW pending
access requests and comments (since last run, tracked in .lastseen.json) and
prints a Telegram-ready digest for the administrator, including the exact
approve/deny commands. If nothing new, prints "OK: nothing pending".

This script only READS and reports. Applying decisions is done by the
administrator replying in Telegram, which the agent executes via bin/atlas_mod.py.
"""
import sys
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from access import AccessStore  # noqa: E402

SEEN = ROOT / "data" / ".lastseen.json"


def load_seen():
    if SEEN.exists():
        try:
            return json.load(open(SEEN))
        except Exception:
            return {}
    return {}


def save_seen(d):
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    json.dump(d, open(SEEN, "w"))


def main():
    store = AccessStore()
    seen = load_seen()
    seen_req = set(seen.get("requests", []))
    seen_comments = set(seen.get("comments", []))

    new_req = [r for r in store.pending_request_list() if r["token"] not in seen_req]
    new_comments = [c for c in store.pending_comments() if c["id"] not in seen_comments]

    lines = []
    if not new_req and not new_comments:
        print("OK: nothing pending since last check.")
        return

    lines.append("⚡ ATLAS CAPITAL — action needed")
    if new_req:
        lines.append(f"\n🔑 {len(new_req)} new access request(s):")
        for r in new_req:
            lines.append(f"• {r['username']} — {r.get('note','')[:60]}")
            lines.append(f"   approve: python3 /Users/it/Project_Atlas/bin/atlas_mod.py approve req {r['token']}")
            lines.append(f"   deny:    python3 /Users/it/Project_Atlas/bin/atlas_mod.py deny req {r['token']}")
    if new_comments:
        lines.append(f"\n💬 {len(new_comments)} new comment(s) pending:")
        for c in new_comments:
            lines.append(f"• [{c['user']}] {c['text'][:80]}")
            lines.append(f"   approve: python3 /Users/it/Project_Atlas/bin/atlas_mod.py approve comment {c['id']}")
            lines.append(f"   deny:    python3 /Users/it/Project_Atlas/bin/atlas_mod.py deny comment {c['id']}")

    # record what we've announced so we don't nag repeatedly
    seen["requests"] = list(seen_req) + [r["token"] for r in new_req]
    seen["comments"] = list(seen_comments) + [c["id"] for c in new_comments]
    save_seen(seen)

    print("\n".join(lines))


if __name__ == "__main__":
    main()
