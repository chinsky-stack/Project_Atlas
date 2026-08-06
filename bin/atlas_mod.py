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
        ok = store.approve_comment(cid) if action == "approve" else store.deny_comment(cid)
        print("COMMENT APPROVED" if (ok and action == "approve") else
              "COMMENT DENIED" if (ok and action == "deny") else "FAILED (id not found / not pending)")
    else:
        print("unknown kind:", kind)
        sys.exit(2)


if __name__ == "__main__":
    main()
