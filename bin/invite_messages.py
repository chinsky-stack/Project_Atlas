# ATLAS CAPITAL — friend invitation (email)
# Personalized intro from the Atlas assistant, sent by Dr. King.
# Recipients: Dr. King (To) + CC (ilyatorchinsky@gmail.com) + BCC (pennmou@gmail.com).

SUBJECT = "You're invited to ATLAS CAPITAL — a members-only trading research portal"

PORTAL_URL = "https://portal.ilyatorchinsky.com"

EMAIL_BODY = f"""Hi Penn,

I wanted to pull you into something I've been building — ATLAS CAPITAL, a
private, members-only research portal for Soros-style, high-conviction trading
ideas. It's running live on its permanent address, and your access is already
approved, so you can log in right away.

This isn't a public app — it's an invitation-only circle. Anything posted in
the portal is moderated by me so it stays a clean, intentional little community.

Your login:
  Portal:   {PORTAL_URL}
  Passphrase (portal gate): atlas2026
  Username: penn
  Password: penn-atlas-2026   (please change it after first login — Account tab)

How to get in:
  1. Open {PORTAL_URL}
  2. Enter the passphrase atlas2026, then sign in with username "penn".
  3. Explore the tabs — Mission Control, New Idea, Risk Office, Trade Journal,
     Markets, and Member Comments. Drop your thoughts in Member Comments;
     I'll review and publish them.

What I'm asking of you: log in, kick the tires, and contribute. Ideas,
critiques, UI gripes, market takes — all welcome. This is the feedback loop
that makes the next version better.

Where this is going: once we've shaken out the rough edges, the next step is to
go live (connect a real broker, paper-first, safety-gated) and turn this into a
proper mobile app. You're in on the ground floor.

Talk soon,
— Dr. King (via ATLAS CAPITAL)

---
ATLAS CAPITAL is a private research and simulation environment. Nothing here is
investment advice or a solicitation. All trading shown is simulated unless a live
broker is explicitly enabled by the administrator.
"""

SMS_BODY = (
    "Hey — Dr. King here. I built ATLAS CAPITAL, a private trading-research "
    "portal, and your access is ready. Open: " + PORTAL_URL + " → passphrase "
    "atlas2026 → sign in as 'penn' / password 'penn-atlas-2026' (change it "
    "after login). Explore and leave thoughts in Member Comments. Next step: "
    "go live + a real app."
)

if __name__ == "__main__":
    print("SUBJECT:", SUBJECT)
    print("URL:", PORTAL_URL)
    print("---- EMAIL ----")
    print(EMAIL_BODY)
    print("---- SMS ----")
    print(SMS_BODY)
