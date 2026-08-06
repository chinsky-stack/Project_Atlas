#!/usr/bin/env python3
"""
Send the ATLAS CAPITAL invitation email from Dr. King's Gmail.

Sends TO Dr. King (self) and BCCs the two friends.
Credentials come from config.local.yaml (gitignored) or env vars:
  gmail_address: your full Gmail address
  gmail_app_password: 16-char Gmail App Password (NOT your normal password)

Requires: pip install yagmail  (or uses sendmail if configured)
Falls back to /usr/bin/mail via a local msmtp-style send if yagmail absent.
"""
import sys
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))
from invite_messages import SUBJECT, EMAIL_BODY, PORTAL_URL  # noqa: E402

# Recipients (override via env if needed)
TO_SELF = os.getenv("ATLAS_TO_SELF", "itorchinsky@alaska.edu")
CC = os.getenv("ATLAS_CC", "ilyatorchinsky@gmail.com").split(",") if os.getenv("ATLAS_CC") else ["ilyatorchinsky@gmail.com"]
BCC = os.getenv("ATLAS_BCC", "pennmou@gmail.com").split(",") if os.getenv("ATLAS_BCC") else ["pennmou@gmail.com"]


def load_creds():
    # 1) env
    addr = os.getenv("GMAIL_ADDRESS")
    pw = os.getenv("GMAIL_APP_PASSWORD")
    # 2) config.local.yaml
    if not addr or not pw:
        cfg = ROOT / "config.local.yaml"
        if cfg.exists():
            try:
                import yaml
                d = yaml.safe_load(open(cfg))
                addr = addr or d.get("gmail_address", "")
                pw = pw or d.get("gmail_app_password", "")
            except Exception:
                pass
    if not addr or not pw:
        print("ERROR: missing Gmail credentials. Set GMAIL_ADDRESS + GMAIL_APP_PASSWORD "
              "env vars, or put gmail_address/gmail_app_password in config.local.yaml.")
        sys.exit(2)
    if not TO_SELF:
        print("ERROR: set ATLAS_TO_SELF to your own email (the 'To' recipient).")
        sys.exit(2)
    return addr, pw


def main():
    addr, pw = load_creds()
    msg = EmailMessage()
    msg["Subject"] = SUBJECT
    msg["From"] = f"Dr. King (ATLAS CAPITAL) <{addr}>"
    msg["To"] = TO_SELF
    msg["Cc"] = ", ".join(CC)
    msg["Bcc"] = ", ".join(BCC)
    msg.set_content(EMAIL_BODY)

    # Gmail SMTP submission
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
        s.login(addr, pw)
        s.send_message(msg)
    print(f"Sent invitation: To={TO_SELF}  Cc={CC}  Bcc={BCC}")


if __name__ == "__main__":
    main()
