# ATLAS CAPITAL — friend invitation (email + SMS text)
# Personalized intro from the Atlas assistant, sent by Dr. King.
# Recipients: Dr. King (To) + BCC alaskamatt@gmail.com, pennmou@gmail.com

SUBJECT = "You're invited to ATLAS CAPITAL — a members-only trading research portal"

PORTAL_URL = "https://nine-instructions-break-virgin.trycloudflare.com"

EMAIL_BODY = f"""Hi Matt & Penn,

I wanted to pull you both into something I've been building — ATLAS CAPITAL, a
private, members-only research portal for Soros-style, high-conviction trading
ideas. It's still in simulation (no real money yet), but it's live and running,
and I'd love for you to log in, poke around, and tell me what you think.

This isn't a public app — it's an invitation-only circle. I'll approve your
access personally, and anything you post in the portal is moderated by me so it
stays a clean, intentional little community.

How to get in:
  1. Open the portal: {PORTAL_URL}
  2. Click "Request Access" and pick a username + password.
  3. I'll get a ping and approve you within a few minutes.
  4. Once you're in, explore the tabs — Mission Control, New Idea, Risk Office,
     Trade Journal, Markets, and Member Comments. Drop your thoughts in the
     Member Comments tab; I'll review and publish them.

What I'm asking of you: log in, kick the tires, and contribute. Ideas,
critiques, UI gripes, market takes — all welcome. This is the feedback loop
that makes the next version better.

Where this is going: once we've shaken out the rough edges together, the next
step is to go live (connect a real broker, paper-first, safety-gated) and turn
this into a proper mobile app. You're in on the ground floor.

Talk soon,
— Dr. King (via ATLAS CAPITAL)

---
ATLAS CAPITAL is a private research and simulation environment. Nothing here is
investment advice or a solicitation. All trading shown is simulated unless a live
broker is explicitly enabled by the administrator.
"""

SMS_BODY = (
    "Hey — Dr. King here. I built ATLAS CAPITAL, a private trading-research "
    "portal, and wanted you in. Open this: " + PORTAL_URL + " → click 'Request "
    "Access', pick a username + password, and I'll approve you in a few minutes. "
    "Log in, explore, and leave thoughts in Member Comments. Next step: go live + "
    "a real app. Check your email for the full intro."
)

if __name__ == "__main__":
    print("SUBJECT:", SUBJECT)
    print("URL:", PORTAL_URL)
    print("---- EMAIL ----")
    print(EMAIL_BODY)
    print("---- SMS ----")
    print(SMS_BODY)
