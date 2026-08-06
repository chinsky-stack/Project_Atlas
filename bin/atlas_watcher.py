#!/usr/bin/env python3
"""
ATLAS CAPITAL — access watcher.

Run on a schedule (Hermes cron). Detects NEW, actionable events since the last
run and prints a Telegram-ready digest for the administrator:
  * new access requests (with approve/deny commands)
  * new pending comments (with approve/deny commands)
  * new FAILED login attempts (unknown user / not approved / bad password)
  * (optional) new successful logins — off by default to reduce noise; flip
    REPORT_SUCCESSFUL_LOGINS below.

If there is NOTHING new, it prints exactly "OK: nothing pending" and the cron
stays silent (see cron prompt). State is tracked in data/.lastseen.json.

This script only READS and reports. Decisions are applied by the administrator
replying in Telegram, which the agent executes via bin/atlas_mod.py.
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from access import AccessStore  # noqa: E402

SEEN = ROOT / "data" / ".lastseen.json"
REPORT_SUCCESSFUL_LOGINS = False  # set True if you want a ping on every login


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
    seen_logins = set(seen.get("logins", []))

    new_req = [r for r in store.pending_request_list() if r["token"] not in seen_req]
    new_comments = [c for c in store.pending_comments() if c["id"] not in seen_comments]

    events = store.recent_login_events(limit=200)
    # filter to events we haven't reported yet, by stable fingerprint
    def fp(e):
        return f"{e['username']}|{e['ok']}|{e['reason']}|{e['at']}"

    new_logins = [e for e in events if fp(e) not in seen_logins]
    new_login_fps = [fp(e) for e in new_logins]
    unseen_failed = [e for e in new_logins if not e["ok"]]
    unseen_ok = [e for e in new_logins if e["ok"]]

    if not new_req and not new_comments and not new_login_fps:
        print("OK: nothing pending")
        return

    lines = ["⚡ ATLAS CAPITAL — activity"]
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
    if unseen_failed:
        lines.append(f"\n⚠️ {len(unseen_failed)} failed login attempt(s):")
        for e in unseen_failed:
            who = e["username"] or "(blank)"
            why = {"unknown_user": "unknown username", "not_approved": "account not approved", "bad_password": "wrong password"}[e["reason"]]
            lines.append(f"• {who} — {why} @ {e['at']}")
    if REPORT_SUCCESSFUL_LOGINS and unseen_ok:
        lines.append(f"\n✅ {len(unseen_ok)} successful login(s):")
        for e in unseen_ok:
            lines.append(f"• {e['username']} @ {e['at']}")

    # mark everything seen
    seen["requests"] = list(seen_req) + [r["token"] for r in new_req]
    seen["comments"] = list(seen_comments) + [c["id"] for c in new_comments]
    seen["logins"] = list(seen_logins) + new_login_fps
    save_seen(seen)

    print("\n".join(lines))


if __name__ == "__main__":
    main()
