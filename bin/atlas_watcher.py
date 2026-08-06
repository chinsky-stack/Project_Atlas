#!/usr/bin/env python3
"""
ATLAS CAPITAL — access watcher (concierge edition).

Run on a schedule (Hermes cron). Detects NEW, actionable events since the last
run and prints a polished, Telegram-ready digest for the administrator:

  * 🔑 new access requests        (with one-tap approve/deny commands)
  * 💬 new pending comments        (with approve/deny commands)
  * ⚠️ failed login attempts        (grouped; brute-force auto-flagged 🚨)
  * ✅ successful logins            (off by default — set REPORT_SUCCESSFUL_LOGINS)

Design goals:
  - Silent when idle (prints "OK: nothing pending" -> cron stays quiet).
  - Each event reported exactly once (fingerprinted in data/.lastseen.json).
  - Brute-force detection: >=3 failed attempts for the same username (or from
    the same IP) in the unseen window is escalated to a security alert.
  - Branded, scannable formatting for a "legit company" feel.

This script only READS and reports. Decisions are applied by the administrator
replying in Telegram, which the agent executes via bin/atlas_mod.py.
"""
import sys
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from access import AccessStore  # noqa: E402

SEEN = ROOT / "data" / ".lastseen.json"
REPORT_SUCCESSFUL_LOGINS = False
BRUTE_THRESHOLD = 3  # failed attempts (same user OR same IP) -> escalate

REASON_TXT = {
    "unknown_user": "unknown username",
    "not_approved": "account pending approval",
    "bad_password": "wrong password",
}

WHY_CMD = {
    "req": "python3 /Users/it/Project_Atlas/bin/atlas_mod.py {verb} req {id}",
    "comment": "python3 /Users/it/Project_Atlas/bin/atlas_mod.py {verb} comment {id}",
}


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


def fp(e):
    return f"{e['username']}|{e['ok']}|{e['reason']}|{e.get('ip','')}|{e['at']}"


def main():
    store = AccessStore()
    seen = load_seen()
    seen_req = set(seen.get("requests", []))
    seen_comments = set(seen.get("comments", []))
    seen_logins = set(seen.get("logins", []))

    new_req = [r for r in store.pending_request_list() if r["token"] not in seen_req]
    new_comments = [c for c in store.pending_comments() if c["id"] not in seen_comments]

    events = store.recent_login_events(limit=200)
    new_logins = [e for e in events if fp(e) not in seen_logins]
    new_login_fps = [fp(e) for e in new_logins]
    unseen_failed = [e for e in new_logins if not e["ok"]]
    unseen_ok = [e for e in new_logins if e["ok"]]

    if not new_req and not new_comments and not new_login_fps:
        print("OK: nothing pending")
        return

    now = datetime.now().strftime("%b %d, %H:%M")
    lines = [
        "⚡ *ATLAS CAPITAL — Security & Access Digest*",
        f"_Generated {now}_",
    ]

    # ---- access requests ----
    if new_req:
        lines.append(f"\n🔑 *{len(new_req)} new access request{'s' if len(new_req)>1 else ''}*")
        for r in new_req:
            note = f" — \"{r.get('note','')[:50]}\"" if r.get("note") else ""
            email = f" ({r.get('email')})" if r.get("email") else ""
            lines.append(f"• *{r['username']}*{email}{note}")
            lines.append(f"   ✅ `atlas_mod.py approve req {r['token']}`")
            lines.append(f"   🚫 `atlas_mod.py deny req {r['token']}`")

    # ---- pending comments ----
    if new_comments:
        lines.append(f"\n💬 *{len(new_comments)} comment{'s' if len(new_comments)>1 else ''} awaiting moderation*")
        for c in new_comments:
            lines.append(f"• [{c['user']}] {c['text'][:70]}")
            lines.append(f"   ✅ `atlas_mod.py approve comment {c['id']}`")
            lines.append(f"   🚫 `atlas_mod.py deny comment {c['id']}`")

    # ---- failed logins (grouped + brute-force detection) ----
    if unseen_failed:
        by_user = Counter(e["username"] or "(blank)" for e in unseen_failed)
        by_ip = Counter(e.get("ip", "unknown") for e in unseen_failed)
        brute_users = {u: n for u, n in by_user.items() if n >= BRUTE_THRESHOLD}
        brute_ips = {i: n for i, n in by_ip.items() if n >= BRUTE_THRESHOLD}

        if brute_users or brute_ips:
            lines.append("\n🚨 *SECURITY ALERT — possible brute-force*")
            if brute_users:
                for u, n in brute_users.items():
                    lines.append(f"• {n} failed attempts on `{u}`")
            if brute_ips:
                for i, n in brute_ips.items():
                    lines.append(f"• {n} failed attempts from IP `{i}`")
            lines.append("  Recommend: deny any matching request; consider blocking the IP at the tunnel.")

        lines.append(f"\n⚠️ *{len(unseen_failed)} failed login attempt{'s' if len(unseen_failed)>1 else ''}*")
        # show one line per attempt, but collapse repeats of same user+reason
        shown = Counter((e["username"] or "(blank)", REASON_TXT.get(e["reason"], e["reason"]), e.get("ip", "unknown"))
                        for e in unseen_failed)
        for (who, why, ip), n in shown.items():
            mult = f" ×{n}" if n > 1 else ""
            lines.append(f"• `{who}` — {why}{mult}  _({ip})_")

    # ---- successful logins ----
    if REPORT_SUCCESSFUL_LOGINS and unseen_ok:
        lines.append(f"\n✅ *{len(unseen_ok)} successful login{'s' if len(unseen_ok)>1 else ''}*")
        for e in unseen_ok:
            lines.append(f"• `{e['username']}`  _({e.get('ip','unknown')})_")

    lines.append("\n— Reply with the command above and I'll execute it.")

    # mark everything seen
    seen["requests"] = list(seen_req) + [r["token"] for r in new_req]
    seen["comments"] = list(seen_comments) + [c["id"] for c in new_comments]
    seen["logins"] = list(seen_logins) + new_login_fps
    save_seen(seen)

    print("\n".join(lines))


if __name__ == "__main__":
    main()
