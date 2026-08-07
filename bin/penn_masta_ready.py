"""One-time note to Penn: MASTA account is ready (he trades it himself),
and Dr. King's other account is auto-traded by Hermes. Professional letter."""

import os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bin.mailer import send_email
import yaml

cfg = yaml.safe_load(open("config.yaml"))
loc = yaml.safe_load(open("config.local.yaml"))


def m(b, o):
    for k, v in o.items():
        if isinstance(v, dict) and isinstance(b.get(k), dict):
            m(b[k], v)
        else:
            b[k] = v


m(cfg, loc)
mail = cfg["mail"]
os.environ["GMAIL_ADDRESS"] = mail["gmail_address"]
os.environ["GMAIL_APP_PASSWORD"] = mail["gmail_app_password"]

to_addr = mail.get("digest_to", "pennmou@gmail.com")

subject = "Your ATLAS CAPITAL paper account (MASTA) is ready"

body = f"""<html><body style="font-family:-apple-system,Segoe UI,Arial;color:#222;max-width:640px;margin:auto;line-height:1.6">
<p>Hi Penn,</p>

<p>Good news — your own ATLAS CAPITAL paper trading account is set up and ready to use. We've named it <b>MASTA</b>, and it's funded with <b>$500,000 in paper (simulated) capital</b>.</p>

<p>You can trade it <b>any way you like</b>. Buy, sell, options, whatever you want to experiment with — it's your sandbox, and there's no risk because it's all simulated. Log in with your own Alpaca credentials and go to town.</p>

<p>One thing worth knowing: alongside your account, Dr. King has a <b>separate</b> ATLAS account that <b>Hermes trades automatically</b> — a rules-based engine that places its own paper trades on a disciplined, risk-managed system. That one is Dr. King's; yours is yours. Two separate books, same ATLAS CAPITAL framework.</p>

<p>From my side, I can <b>see your MASTA account</b> (balances, positions, orders) so we can follow along with what you're doing — but I won't touch it. It's your account to trade. If you ever want to talk through an idea, just email Dr. King and start with <b>"Hermes:"</b> and I'll answer right away.</p>

<p>Welcome aboard — have fun with it.</p>

<p style="margin-top:18px">— Hermes (ATLAS CAPITAL)</p>
</body></html>"""

send_email(subject, body, to_addr, cc_addr=mail.get("digest_cc", ""))
print("Sent MASTA-ready note to", to_addr)
