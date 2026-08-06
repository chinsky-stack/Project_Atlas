"""
Access control + moderation for Project Atlas (branded member portal).

Design (per Dr. King's requirements):
  * Friends get access ONLY after Dr. King approves them here on Telegram.
  * Each friend has a username + password (bcrypt-hashed, never plaintext).
  * A cap (max_members) limits how many can be approved.
  * Comments are submitted by members but are HIDDEN until Dr. King approves
    them here on Telegram (human-in-the-loop moderation).
  * The watcher (src/access_watcher or a cron) notifies Dr. King on Telegram
    whenever there is a new access request or a new pending comment, and
    applies his approve/deny replies back into this store.

All state lives in data/access.json. No secrets, no external services.
"""

from __future__ import annotations

import json
import threading
import hashlib
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


# Use bcrypt if available; otherwise a salted SHA-256 fallback (still hashed).
try:
    import bcrypt  # type: ignore
    _HAVE_BCRYPT = True
except Exception:
    _HAVE_BCRYPT = False


def _hash(password: str, salt: Optional[str] = None) -> str:
    if _HAVE_BCRYPT:
        import bcrypt as _bc  # local alias to satisfy static analysis
        if salt is None:
            return _bc.hashpw(password.encode(), _bc.gensalt()).decode()
        return password  # unused
    salt = salt or secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"sha256${salt}${h}"


def check_password(password: str, stored: str) -> bool:
    if stored.startswith("sha256$"):
        _, salt, h = stored.split("$", 2)
        return h == hashlib.sha256((salt + password).encode()).hexdigest()
    if _HAVE_BCRYPT:
        try:
            return bcrypt.checkpw(password.encode(), stored.encode())
        except Exception:
            return False
    return False


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class AccessStore:
    def __init__(self, path: Optional[Path] = None, max_members: int = 6):
        self.path = path or (Path(__file__).parent.parent / "data" / "access.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_members = max_members
        self._lock = threading.RLock()
        self.data = self._load()

    # ---------------- persistence ----------------
    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "members": {},          # username -> {pw_hash, approved, role, email, created, approved_at}
            "pending_requests": {}, # token -> {username, email, note, created}
            "comments": [],         # {id, user, text, status, created, decided_at}
            "seq": 0,
        }

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def _next_id(self) -> int:
        self.data["seq"] = self.data.get("seq", 0) + 1
        return self.data["seq"]

    # ---------------- access requests ----------------
    def request_access(self, username: str, password: str, email: str = "", note: str = "") -> str:
        username = username.strip().lower()
        with self._lock:
            if username in self.data["members"]:
                raise ValueError("That username is already registered.")
            token = secrets.token_urlsafe(12)
            self.data["pending_requests"][token] = {
                "username": username,
                "pw_hash": _hash(password) if _HAVE_BCRYPT else _hash(password),
                "email": email,
                "note": note,
                "created": _now(),
            }
            self._save()
            return token

    def pending_request_list(self) -> List[dict]:
        with self._lock:
            return [
                {"token": t, **v} for t, v in self.data["pending_requests"].items()
            ]

    def approve_request(self, token: str) -> bool:
        with self._lock:
            req = self.data["pending_requests"].get(token)
            if not req:
                return False
            approved_count = sum(1 for m in self.data["members"].values() if m.get("approved"))
            if approved_count >= self.max_members:
                return False  # cap reached
            self.data["members"][req["username"]] = {
                "pw_hash": req["pw_hash"],
                "approved": True,
                "role": "member",
                "email": req.get("email", ""),
                "note": req.get("note", ""),
                "created": req["created"],
                "approved_at": _now(),
            }
            del self.data["pending_requests"][token]
            self._save()
            return True

    def deny_request(self, token: str) -> bool:
        with self._lock:
            if token in self.data["pending_requests"]:
                del self.data["pending_requests"][token]
                self._save()
                return True
            return False

    # ---------------- login ----------------
    def authenticate(self, username: str, password: str, ip: str = "") -> Optional[dict]:
        username = username.strip().lower()
        with self._lock:
            m = self.data["members"].get(username)
            if not m or not m.get("approved"):
                reason = "unknown_user" if username not in self.data["members"] else "not_approved"
                self._record_login(username, ok=False, reason=reason, ip=ip)
                return None
            if check_password(password, m["pw_hash"]):
                self._record_login(username, ok=True, reason="success", ip=ip)
                return m
            self._record_login(username, ok=False, reason="bad_password", ip=ip)
            return None

    def _record_login(self, username: str, ok: bool, reason: str, ip: str = ""):
        with self._lock:
            self.data.setdefault("login_events", []).append({
                "username": username,
                "ok": ok,
                "reason": reason,
                "ip": ip or "unknown",
                "at": _now(),
            })
            # keep last 200 events
            if len(self.data["login_events"]) > 200:
                self.data["login_events"] = self.data["login_events"][-200:]
            self._save()

    def recent_login_events(self, limit: int = 50) -> List[dict]:
        with self._lock:
            return list(reversed(self.data.get("login_events", [])[-limit:]))

    def is_approved(self, username: str) -> bool:
        with self._lock:
            m = self.data["members"].get(username)
            return bool(m and m.get("approved"))

    def approved_members(self) -> List[str]:
        with self._lock:
            return [u for u, m in self.data["members"].items() if m.get("approved")]

    # ---------------- comments (moderated) ----------------
    def add_comment(self, user: str, text: str) -> int:
        text = text.strip()
        if not text:
            raise ValueError("Empty comment.")
        with self._lock:
            cid = self._next_id()
            self.data["comments"].append({
                "id": cid,
                "user": user,
                "text": text,
                "status": "pending",
                "created": _now(),
                "decided_at": "",
            })
            self._save()
            return cid

    def pending_comments(self) -> List[dict]:
        with self._lock:
            return [c for c in self.data["comments"] if c["status"] == "pending"]

    def visible_comments(self) -> List[dict]:
        with self._lock:
            return [c for c in self.data["comments"] if c["status"] == "approved"]

    def approve_comment(self, cid: int) -> bool:
        with self._lock:
            for c in self.data["comments"]:
                if c["id"] == cid and c["status"] == "pending":
                    c["status"] = "approved"
                    c["decided_at"] = _now()
                    self._save()
                    return True
            return False

    def deny_comment(self, cid: int) -> bool:
        with self._lock:
            for c in self.data["comments"]:
                if c["id"] == cid and c["status"] == "pending":
                    c["status"] = "denied"
                    c["decided_at"] = _now()
                    self._save()
                    return True
            return False

    # ---------------- watcher digest ----------------
    def pending_digest(self) -> dict:
        """What the Telegram watcher should surface to Dr. King right now."""
        with self._lock:
            return {
                "access_requests": self.pending_request_list(),
                "comments": self.pending_comments(),
            }
