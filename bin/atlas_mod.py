#!/usr/bin/env python3
"""
ATLAS CAPITAL — access moderator CLI.

Used by the administrator (Dr. King) to approve/deny friend access requests
and member comments. Invoked from Telegram replies, e.g.:

  python3 bin/atlas_mod.py approve req <TOKEN>
  python3 bin/atlas_mod.py deny   req <TOKEN>
  python3 bin/atlas_mod.py approve comment <ID>
  python3 bin/atlas_mod.py deny   comment <ID>
  python3 bin/atlas_mod.py reset  pw <USER> <NEWPASSWORD>
  python3 bin/atlas_mod.py add    member <USER> <EMAIL> <PASSWORD>
  python3 bin/atlas_mod.py list

All changes persist to data/access.json. No network calls.
"""
import sys
import os
from pathlib import Path

# make src importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from access import AccessStore  # noqa: E402


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "list"):
        store = AccessStore()
        print("== Pending access requests ==")
        for r in store.pending_request_list():
            print(f"  req  {r['token']}  user={r['username']}  note={r.get('note','')}")
        print("== Pending comments ==")
        for c in store.pending_comments():
            print(f"  comment {c['id']}  user={c['user']}  text={c['text'][:80]}")
        print("== Approved members ==")
        print(" ", store.approved_members())
        return

    # ---- suggestion follow-up: atlas_mod.py suggestion <id> <approve|decline|change> [note] ----
    if args[0].lower() == "suggestion":
        if len(args) < 3:
            print("usage: atlas_mod.py suggestion <ID> <approve|decline|change> [note...]")
            sys.exit(2)
        iid = args[1]
        decision = args[2].lower()
        note = " ".join(args[3:]) if len(args) > 3 else ""
        from improvements import set_status, all_items
        item = next((i for i in all_items() if i["id"] == iid), None)
        if not item:
            print("suggestion not found:", iid)
            sys.exit(1)
        status = {"approve": "accepted", "decline": "rejected", "change": "changed"}[decision]
        set_status(iid, status, note)
        # follow-up email to the source if we have an address
        src = item["source"]
        addr = None
        if src.startswith("Penn"):
            addr = "pennmou@gmail.com"
        if addr:
            import yaml
            cfg = yaml.safe_load(open("config.yaml")); loc = yaml.safe_load(open("config.local.yaml"))
            def m(b,o):
                for k,v in o.items():
                    if isinstance(v,dict) and isinstance(b.get(k),dict): m(b[k],v)
                    else: b[k]=v
            m(cfg,loc)
            mail = cfg.get("mail", {})
            os.environ["GMAIL_ADDRESS"]=mail["gmail_address"]; os.environ["GMAIL_APP_PASSWORD"]=mail["gmail_app_password"]
            from bin.inbound_monitor import _letter, send_reply
            name = "Penn" if addr=="pennmou@gmail.com" else src.split()[0]
            verdict = {"accepted":"we're moving forward with it","rejected":"we've decided not to move forward","changed":"we'll do a revised version"}[status]
            paras = [
                f"Hi {name},",
                f"Thank you again for the suggestion about: \u201c{item['text'][:200]}\u201d.",
                f"Dr. King and I reviewed it. The outcome: {verdict}.",
            ]
            if note:
                paras.append(f"Notes on the decision: {note}")
            paras.append("We genuinely appreciate you shaping ATLAS CAPITAL with us, and we'll keep you posted as things evolve.")
            html = _letter(paras)
            send_reply(addr, f"Re: your ATLAS CAPITAL suggestion ({iid})", html, cfg,
                       f"Hi {name}, thanks again for the suggestion ({iid}). Outcome: {verdict}. {'Note: '+note if note else ''} (ATLAS CAPITAL)")
            print(f"SUGGESTION {iid} -> {status}; follow-up emailed to {addr}")
        else:
            print(f"SUGGESTION {iid} -> {status} (no email address for source '{src}'; tell Dr. King to relay)")
        return

    action = args[0].lower()  # approve | deny | reset | add
    if action not in ("approve", "deny", "reset", "add"):
        print("usage: atlas_mod.py [approve|deny] [req <token> | comment <id>]")
        print("       atlas_mod.py reset pw <USER> <NEWPASSWORD>")
        print("       atlas_mod.py add member <USER> <EMAIL> <PASSWORD>")
        sys.exit(2)

    kind = args[1].lower() if len(args) > 1 else ""
    target = args[2] if len(args) > 2 else ""

    store = AccessStore()
    if action == "add":
        if kind != "member" or not target or len(args) < 5:
            print("usage: atlas_mod.py add member <USER> <EMAIL> <PASSWORD>")
            sys.exit(2)
        email = args[3]
        new_pw = args[4]
        ok = store.add_member(target, email, new_pw)
        print("MEMBER ADDED" if ok else
              "FAILED (username exists, cap reached, or bad input)")
        return

    if action == "reset":
        if kind != "pw" or not target or len(args) < 4:
            print("usage: atlas_mod.py reset pw <USER> <NEWPASSWORD>")
            sys.exit(2)
        new_pw = args[3]
        try:
            ok = store.reset_password(target, new_pw)
            print("PASSWORD RESET" if ok else "FAILED (user not found)")
        except ValueError as e:
            print("FAILED:", e)
        return

    if kind == "req":
        if action == "approve":
            ok = store.approve_request(target)
            print("ACCESS APPROVED" if ok else "FAILED (token invalid, cap reached, or already handled)")
        else:
            ok = store.deny_request(target)
            print("ACCESS DENIED" if ok else "FAILED (token not found)")
    elif kind == "comment":
        cid = int(target)
        if action == "approve":
            # capture comment text before approval for suggestion logging
            c = None
            try:
                for x in store.data.get("comments", []):
                    if x.get("id") == cid:
                        c = x
                        break
            except Exception:
                c = None
            ok = store.approve_comment(cid)
            print("COMMENT APPROVED" if ok else "FAILED (id not found / not pending)")
            if ok and c:
                try:
                    from improvements import add as log_suggestion, looks_like_suggestion
                    txt = c.get("text") or ""
                    who = c.get("user") or "member"
                    if looks_like_suggestion(txt):
                        item = log_suggestion(f"{who} (portal comment)", txt[:500])
                        print(f"SUGGESTION LOGGED {item['id']} from {who}")
                except Exception as e:
                    print("suggestion-log skipped:", e)
        else:
            ok = store.deny_comment(cid)
            print("COMMENT DENIED" if ok else "FAILED (id not found)")
    else:
        print("unknown kind:", kind)
        sys.exit(2)


if __name__ == "__main__":
    main()
