"""Shared Gmail SMTP mailer for ATLAS CAPITAL.

Sends HTML email via Gmail SMTP. App password is passed via env (spaced form
accepted by Gmail). Recipients passed explicitly.
"""
import os
import smtplib
import ssl
from email.message import EmailMessage


def send_email(subject: str, html_body: str,
               to_addr: str, cc_addr: str | None = None,
               bcc_addr: str | None = None,
               from_name: str = "Dr. King (ATLAS CAPITAL)") -> None:
    """Send an HTML email. Raises on failure.

    to_addr: primary recipient
    cc_addr: comma-separated CC (optional)
    bcc_addr: comma-separated BCC (optional)
    """
    addr = os.getenv("GMAIL_ADDRESS", "")
    pw = os.getenv("GMAIL_APP_PASSWORD", "")  # spaced form works
    if not addr or not pw:
        raise RuntimeError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD env not set")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{addr}>"
    msg["To"] = to_addr
    if cc_addr:
        msg["Cc"] = cc_addr
    msg.set_content("This message is HTML. Please use an HTML-capable mail client.")
    msg.add_alternative(html_body, subtype="html")

    recipients = [to_addr]
    if cc_addr:
        recipients += [a.strip() for a in cc_addr.split(",") if a.strip()]
    if bcc_addr:
        recipients += [a.strip() for a in bcc_addr.split(",") if a.strip()]

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
        s.login(addr, pw)
        s.send_message(msg, to_addrs=recipients)
    print(f"Sent: To={to_addr} Cc={cc_addr} Bcc={bcc_addr}")
