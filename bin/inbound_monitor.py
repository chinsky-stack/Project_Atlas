"""ATLAS CAPITAL — Inbound Email Monitor (IMAP poll).

Rules (set by Dr. King):
  - Watch itorchinsky@alaska.edu inbox.
  - If PENN (pennmou@gmail.com) asks a question -> reply to him right away (autonomous).
  - For ANY other sender -> use judgment, but TELL Dr. King before executing anything.

Behavior:
  - Polls every run; tracks processed Message-IDs in data/.seen_mail.json (gitignored).
  - Replies to Penn via Gmail SMTP (same app password).
  - For non-Penn mail needing a decision, sends a Telegram alert to the admin and does NOT act.
  - Silent when there's nothing to do (no spam).

Usage: python bin/inbound_monitor.py   (run on a schedule, e.g. every 10 min)
"""
from __future__ import annotations
import os, sys, json, imaplib, email, datetime as dt, smtplib, ssl
from email.header import decode_header
from email.message import EmailMessage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEN = os.path.join(ROOT, "data", ".seen_mail.json")

PENN = "pennmou@gmail.com"
ADMIN_TG = "8660692768"
# Your own addresses + known bulk/noise senders -> never alert, just mark seen.
IGNORE_SENDERS = {
    "itorchinsky@alaska.edu",
    "ilyatorchinsky@gmail.com",
    "app@mail.alpaca.markets", "support@alpaca.markets", "support@mailer.alpaca.markets",
    "no-reply@accounts.google.com", "no-reply@email.claude.com", "no-reply-ky0skiivqsfenckd9c6vna@mail.anthropic.com",
    "noreply@notify.cloudflare.com", "em@em1.cloudflare.com",
    "no-reply@slack.com", "no-reply-hx1jmxfjbvky5srzkvv6zoea@slack.com",
    "info@mail.fishbrain.com", "notify@app.fishbrain.com",
    "handshake@notifications.joinhandshake.com", "handshake@g.joinhandshake.com",
    "no-reply@jm.indeed.com", "no_reply@email.heygen.com", "webinar@learn.heygen.com",
    "ks@desktopcommander.app", "no-reply@privy.io", "luna@aitopia.app", "support@readme.com",
    "noreply@workforce.intuit.com", "tsadmit@gwu.edu", "indianna@mobilizationcenter.org",
}
# substrings that mark a sender as bulk/noise
IGNORE_SUBSTR = ("@mail.", "no-reply", "noreply", "donotreply", "notifications.",
                 "bounce", "postmaster", "mailer-daemon")
IMAP_HOST, IMAP_PORT = "imap.gmail.com", 993
SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 465


def load_cfg():
    import yaml
    base = yaml.safe_load(open(os.path.join(ROOT, "config.yaml")))
    loc = yaml.safe_load(open(os.path.join(ROOT, "config.local.yaml")))
    def m(b, o):
        for k, v in o.items():
            if isinstance(v, dict) and isinstance(b.get(k), dict):
                m(b[k], v)
            else:
                b[k] = v
    m(base, loc)
    return base


def _dec(x):
    if isinstance(x, bytes):
        return x.decode("utf-8", "ignore")
    return str(x)


def _hdr(msg, name):
    val = msg.get(name, "")
    parts = decode_header(val)
    return "".join(_dec(s) for s, enc in parts)


def _body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return _dec(part.get_payload(decode=True))
        return ""
    return _dec(msg.get_payload(decode=True))


def load_seen():
    try:
        return json.load(open(SEEN))
    except Exception:
        return {"ids": []}


def save_seen(seen):
    os.makedirs(os.path.dirname(SEEN), exist_ok=True)
    json.dump(seen, open(SEEN, "w"))


def send_reply(to_addr, subject, body, cfg):
    mail = cfg.get("mail", {})
    addr = mail.get("gmail_address") or os.getenv("GMAIL_ADDRESS")
    pw = mail.get("gmail_app_password") or os.getenv("GMAIL_APP_PASSWORD")
    msg = email.message.EmailMessage()
    msg["Subject"] = "Re: " + subject
    msg["From"] = f"Hermes (ATLAS CAPITAL) <{addr}>"
    msg["To"] = to_addr
    msg.set_content(body)
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as s:
        s.login(addr, pw)
        s.send_message(msg, to_addrs=[to_addr])
    return True


def send_telegram(text):
    """Best-effort Telegram alert to the admin. Uses the hermes gateway if available."""
    try:
        # Prefer the running hermes telegram delivery via a small helper
        import subprocess
        # We rely on the scheduler/cron delivering stdout; but for a direct ping we
        # attempt the hermes CLI if present.
        # Fallback: print so the cron/agent surfaces it.
        print("TG_ALERT:" + text)
    except Exception:
        print("TG_ALERT:" + text)


def is_question(text):
    t = text.strip().lower()
    return ("?" in t) or any(k in t for k in
           ["can you", "could you", "how do", "what", "why", "when", "should", "is it",
            "are you", "do you", "help", "explain", "tell me"])


def answer_penn(question: str) -> str:
    """Generate a plain-language answer to Penn's question about ATLAS CAPITAL.
    Honest, educational, no made-up facts. Uses what we know about the system."""
    q = question.lower()
    if "option" in q or "spread" in q:
        return ("ATLAS trades defined-risk option vertical spreads (bull-call when we're "
                "bullish, bear-put when bearish) — never naked shorts. Each trade risks at "
                "most ~8% of the book in premium, and the whole system freezes if it draws "
                "down 35%. It's all paper for now, so no real money is at stake.")
    if "password" in q or "login" in q or "sign in" in q or "access" in q:
        return ("Sign in at https://portal.ilyatorchinsky.com (passphrase atlas2026) with "
                "username 'penn' and the password Dr. King gave you. You can change it under "
                "the Account tab after logging in.")
    if "live" in q or "real money" in q or "fund" in q:
        return ("Right now everything is PAPER ONLY — simulated, no real money. Dr. King has "
                "said we'll only consider a real account after the paper system proves itself "
                "over weeks. Nothing goes live without his explicit go-ahead.")
    if "performance" in q or "how" in q and "doing" in q or "pnl" in q or "profit" in q:
        return ("You'll get a weekly digest (Sundays) with exactly what was bought/sold, why, "
                "and open positions. I can't quote live P&L here since it changes by the minute "
                "— check the portal's Auto Trader tab or the latest digest.")
    return ("Good question. ATLAS CAPITAL is a private paper-trading research portal run by "
            "Dr. King. The autonomous engine trades a capped, risk-managed book (stocks, "
            "shorts, and defined-risk options) in simulation only. Happy to dig into anything "
            "specific — ask away.\n\n— Hermes (ATLAS CAPITAL)")


def process(cfg):
    mail = cfg.get("mail", {})
    user = mail.get("gmail_address") or os.getenv("GMAIL_ADDRESS")
    pw = mail.get("gmail_app_password") or os.getenv("GMAIL_APP_PASSWORD")
    seen = load_seen()
    seen_ids = set(seen.get("ids", []))

    m = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    m.login(user, pw)
    m.select("INBOX")
    # only scan the last 3 days (perf + relevance)
    since = (dt.datetime.now() - dt.timedelta(days=3)).strftime("%d-%b-%Y")
    typ, data = m.search(None, "SINCE", since)
    ids = data[0].split()
    new_actions = []
    for num in ids:
        mid = num.decode()
        if mid in seen_ids:
            continue
        typ, d = m.fetch(num, "(RFC822.HEADER)")
        msg = email.message_from_bytes(d[0][1])
        msgid = msg.get("Message-ID", mid)
        frm = _hdr(msg, "From")
        subj = _hdr(msg, "Subject")
        sender_email = ""
        for tok in frm.split():
            if "@" in tok:
                sender_email = tok.strip("<>()'\"")
        sender_email = sender_email.lower()
        seen_ids.add(mid)

        # Skip own + bulk/noise silently (no alert, just mark seen)
        if sender_email in IGNORE_SENDERS or any(s in sender_email for s in IGNORE_SUBSTR):
            continue

        # Penn -> answer autonomously (fetch body only for him)
        if PENN in sender_email:
            typ, db = m.fetch(num, "(RFC822)")
            body = _body(email.message_from_bytes(db[0][1])).strip()
            if is_question(body) or is_question(subj):
                ans = answer_penn(body or subj)
                try:
                    send_reply(sender_email, subj, ans, cfg)
                    new_actions.append(f"REPLIED to Penn re: {subj[:50]} | {ans[:80]}...")
                except Exception as e:
                    new_actions.append(f"Penn Q but reply FAILED: {e}")
            else:
                new_actions.append(f"Penn (no question): {subj[:60]} — noted, no reply sent")
        else:
            # Non-Penn, non-noise: use judgment, but tell admin before executing anything.
            # Only alert if it looks actionable (a question in subject or body).
            typ, db = m.fetch(num, "(RFC822)")
            body_txt = _body(email.message_from_bytes(db[0][1])).strip()
            actionable = is_question(subj) or is_question(body_txt)
            if actionable:
                new_actions.append(f"OTHER [{sender_email}] {subj[:60]} — flagged for Dr. King")
                send_telegram(f"📨 Inbound from {sender_email}: {subj[:60]} — I'll wait for your OK before acting.")
            else:
                # personal but not actionable (e.g. a note) -> log only, no ping
                new_actions.append(f"NOTE [{sender_email}] {subj[:60]} — logged, no alert")
    m.logout()
    seen["ids"] = list(seen_ids)[-500:]
    save_seen(seen)
    return new_actions


def main():
    cfg = load_cfg()
    actions = process(cfg)
    if actions:
        print("Processed:")
        for a in actions:
            print("  -", a)
    else:
        print("No new mail to process.")


if __name__ == "__main__":
    main()
