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
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
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


def send_reply(to_addr, subject, html_body, cfg, text_body=None):
    mail = cfg.get("mail", {})
    addr = mail.get("gmail_address") or os.getenv("GMAIL_ADDRESS")
    pw = mail.get("gmail_app_password") or os.getenv("GMAIL_APP_PASSWORD")
    msg = email.message.EmailMessage()
    msg["Subject"] = "Re: " + subject
    msg["From"] = f"Hermes (ATLAS CAPITAL) <{addr}>"
    msg["To"] = to_addr
    msg.set_content(text_body or "This message is HTML. Please use an HTML-capable mail client.")
    msg.add_alternative(html_body, subtype="html")
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as s:
        s.login(addr, pw)
        s.send_message(msg, to_addrs=[to_addr])
    return True


def _letter(paras, signoff="— Hermes (ATLAS CAPITAL)"):
    """Wrap paragraphs in a clean professional HTML letter."""
    body = "".join(f"<p style='margin:0 0 12px 0'>{p}</p>" for p in paras)
    return f"""<html><body style="font-family:-apple-system,Segoe UI,Arial;color:#222;max-width:640px;margin:auto;line-height:1.55">
    {body}
    <p style='margin:0 0 4px 0'>{signoff}</p>
    </body></html>"""


def penn_letter(question, answer_text):
    """Professional reply to Penn: acknowledges, gives proposed ideas,
    marks as subject to Dr. King's approval."""
    paras = [
        "Hi Penn,",
        f"Thanks for writing in. Here are my proposed thoughts on your note "
        f"(&ldquo;{question[:160]}&rdquo;):",
        answer_text,
        "These are <b>proposed ideas, subject to Dr. King's approval</b> &mdash; he reviews "
        "everything before anything is acted on, and nothing changes in the portal or the "
        "trading book without his sign-off. I'll follow up once he's weighed in.",
        "Happy to dig deeper on any of this.",
    ]
    return _letter(paras)


def thank_you_letter(name, about):
    paras = [
        f"Hi {name},",
        f"Thank you for your involvement with ATLAS CAPITAL &mdash; and especially for the "
        f"suggestion about {about}. Dr. King and I read every idea that comes in, and we're "
        f"genuinely glad you're engaging with the project.",
        "We'll look at what (if anything) to implement and how, and I'll follow up with you "
        "once there's a decision &mdash; including if we decide not to move forward, so you "
        "always know the outcome.",
    ]
    return _letter(paras), f"Hi {name}, thank you for the suggestion about {about} — we've logged it and Dr. King will review. (ATLAS CAPITAL)"


def send_telegram(text):
    """Record an IMPORTANT alert to the pending-alerts file. The relay cron
    delivers only these to Telegram — routine scans stay silent."""
    import datetime as _dt
    path = os.path.join(ROOT, "data", ".alerts_pending.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps({
            "ts": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "text": text,
        }) + "\n")



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


def _audit(entry):
    path = os.path.join(ROOT, "data", "inbound_log.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def process(cfg):
    from src.improvements import add as log_suggestion, looks_like_suggestion
    mail = cfg.get("mail", {})
    user = mail.get("gmail_address") or os.getenv("GMAIL_ADDRESS")
    pw = mail.get("gmail_app_password") or os.getenv("GMAIL_APP_PASSWORD")
    seen = load_seen()
    seen_ids = set(seen.get("ids", []))

    m = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    m.login(user, pw)
    m.select("INBOX")
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
        # real-name guess for thank-you letters
        name = sender_email.split("@")[0].split(".")[0].title()
        seen_ids.add(mid)

        # full body (needed for suggestion detection)
        typ, db = m.fetch(num, "(RFC822)")
        body = _body(email.message_from_bytes(db[0][1])).strip()
        is_sugg = looks_like_suggestion(body) or looks_like_suggestion(subj)

        _audit({"ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "from": sender_email, "subject": subj, "suggestion": is_sugg})

        # Skip bulk/noise silently (still audited above)
        if sender_email in IGNORE_SENDERS or any(s in sender_email for s in IGNORE_SUBSTR):
            continue

        # ---- Penn: always engage, professional letter, thank on suggestion ----
        if PENN in sender_email:
            if is_sugg:
                html, plain = thank_you_letter("Penn", subj or body[:60])
                send_reply(sender_email, subj, html, cfg, plain)
                item = log_suggestion("Penn (email)", body[:500])
                new_actions.append(f"PENN SUGGESTION logged {item['id']} -> thanked")
                send_telegram(f"💡 New suggestion from Penn [{item['id']}]: {subj[:50]} — thanked him, awaiting your review.")
            else:
                ans = answer_penn(body or subj)
                html = penn_letter(body or subj, ans)
                send_reply(sender_email, subj, html, cfg, ans)
                new_actions.append(f"REPLIED to Penn re: {subj[:50]}")
                send_telegram(f"✉️ Penn emailed ({'question' if (is_question(body) or is_question(subj)) else 'note'}): {subj[:50]} — Hermes replied (subject to your approval).")

        # ---- Dr. King (you): log suggestions, acknowledge, alert ----
        elif sender_email in ("itorchinsky@alaska.edu", "ilyatorchinsky@gmail.com"):
            if is_sugg:
                item = log_suggestion("Dr. King (email)", body[:500])
                new_actions.append(f"YOUR SUGGESTION logged {item['id']}")
                send_telegram(f"💡 You suggested [{item['id']}]: {subj[:60]} — logged for implementation review.")
            else:
                new_actions.append(f"NOTE from you: {subj[:60]} — logged")
                # not important enough to ping; already audited

        # ---- Other person: flag, alert, log suggestions ----
        else:
            if is_sugg:
                item = log_suggestion(f"{sender_email} (email)", body[:500])
                html, plain = thank_you_letter(name, subj or body[:60])
                send_reply(sender_email, subj, html, cfg, plain)
                new_actions.append(f"OTHER SUGGESTION {item['id']} from {sender_email} -> thanked")
                send_telegram(f"💡 Suggestion from {sender_email} [{item['id']}]: {subj[:50]} — thanked, needs your call.")
            else:
                new_actions.append(f"OTHER [{sender_email}] {subj[:60]} — flagged")
                send_telegram(f"📨 Inbound from {sender_email}: {subj[:60]} — I'll wait for your OK before acting.")

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
