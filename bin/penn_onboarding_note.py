"""One-time note to Penn: how to talk to Hermes + what to look for.

Run once: python bin/penn_onboarding_note.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml
from bin.mailer import send_email

cfg = yaml.safe_load(open("config.yaml"))
loc = yaml.safe_load(open("config.local.yaml"))
def m(b, o):
    for k, v in o.items():
        if isinstance(v, dict) and isinstance(b.get(k), dict): m(b[k], v)
        else: b[k] = v
m(cfg, loc)
mail = cfg.get("mail", {})
os.environ["GMAIL_ADDRESS"] = mail["gmail_address"]
os.environ["GMAIL_APP_PASSWORD"] = mail["gmail_app_password"]

body = """Hi Penn,

Dr. King set up ATLAS CAPITAL as a private paper-trading research portal, and I'm Hermes — the assistant that reads this inbox and answers your questions.

How to reach me:
- Just email Dr. King (itorchinsky@alaska.edu) and start your message with "Hermes:" — I'll read it and reply right away.
- No need to CC anyone; Dr. King sees everything too.

What you can ask me:
- Your login / password (username is "penn"; reset via the Account tab).
- How the trading works — stocks/shorts and defined-risk options spreads, all in simulation (paper) only.
- What's paper vs live (right now it's 100% paper; nothing is real money).
- Where to see performance (the portal's Auto Trader tab, or the weekly digest).
- Anything in the weekly digest.

What to look for week to week:
- The Sunday digest: what was bought/sold, WHY (the signal), open positions, and a discussion on improving returns.
- The portal (https://portal.ilyatorchinsky.com, passphrase atlas2026): Mission Control, New Idea, Risk Office, Trade Journal, Markets, Member Comments, Auto Trader.

What I will NOT do from email:
- I won't change your account or place trades based on an email. Account changes go through Dr. King. I only answer questions.

Fire away any time — start with "Hermes:" and I'll get back to you.

— Hermes (ATLAS CAPITAL)
"""

send_email("Welcome to ATLAS CAPITAL — how to talk to Hermes", body,
           to_addr="pennmou@gmail.com", cc_addr="ilyatorchinsky@gmail.com")
print("Penn onboarding note sent.")
