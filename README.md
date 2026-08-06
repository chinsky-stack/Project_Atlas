# PROJECT ATLAS
### Simple AI-Assisted Trading System (Soros-Style)

**For Dr. King**
Version 0.4 — Simulated live mode + shareable with friends
Starting capital: $1,000 (editable)

This is a complete, self-contained package.
You do **not** need to know how to code.

---

## What this system does
- High-conviction, concentrated positions (Soros style)
- Ruthless cutting of losers (stop orders auto-close losers)
- Aggressive risk limits for a learning account
- **Simulated live mode**: real market prices via yfinance, simulated fills, risk rules enforced in code
- Broker-ready: connect **Alpaca** (paper-first, commission-free) — see `config.yaml` → `broker:`
- Simple dashboard you open in your browser
- Trade journal, idea pipeline, and basic logging
- Shorts and options flags are ON in config (shorts fully wired; options fills stubbed for later)
- **Shareable**: friends can open the same dashboard from their phone/computer over a secure tunnel

---

## How to run it (one click)

From a terminal **in the Project_Atlas folder**:

```bash
bash start_atlas.sh
```

This starts the dashboard AND a secure Cloudflare tunnel, and prints a
**remote URL** + **passphrase** you can send to friends. Both auto-restart
if they crash (important on Starlink).

To make it run automatically whenever you log in:
```bash
launchctl load ~/Library/LaunchAgents/com.projectatlas.daemon.plist
```

---

## Open it from anywhere (phone / away from home)

The dashboard is reachable through a secure HTTPS tunnel — it works even on
Starlink (CGNAT) and behind a VPN, no router port-forwarding needed.

1. Open the **remote URL** printed by `start_atlas.sh` (looks like
   `https://xxxx.trycloudflare.com`).
2. Enter the passphrase (default **`atlas2026`**; set `ATLAS_PASSWORD=xxx`
   to change).

Share that URL + passphrase with your friends. Everyone sees the **same**
live book — good for watching together and reviewing trades.

> Note: the free Cloudflare quick-tunnel URL changes if the Mac reboots.
> For a stable URL later, create a named tunnel (free Cloudflare account)
> or a permanent reverse proxy.

---

## Friend feedback / review

Friends can file bugs, suggestions, and questions as GitHub issues — the
assistant triages and implements them.

- Repo: https://github.com/chinsky-stack/Project_Atlas
- Click **Issues → New issue → Atlas Feedback**
- Pick a type (bug / suggestion / usability / risk-rule concern) and how
  important it is. Paste screenshots directly into the box.
- The assistant reviews new issues and implements safe, agreed changes.

---

## How to set it up from scratch (3 steps)

### Step 1 — Install Python 3.10+ (if you don't have it)
Go to https://www.python.org/downloads/ and install the latest version.
Check the box that says "Add Python to PATH".

### Step 2 — Create the environment
Open a terminal **in the Project_Atlas folder**:
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3 — Run it
```bash
bash start_atlas.sh
```

---

## Changing the starting capital or risk rules
Open `config.yaml` with any text editor. Change the numbers. Save. Restart.

---

## Connecting a broker (next step — paper first)
Edit `config.yaml` under `broker:`:
- `mode: simulate` — default, no broker, no keys (what we're testing now)
- `mode: paper` — Alpaca **paper** sandbox (real API, NO real money).
  Get free paper keys at https://app.alpaca.markets/ and paste them into
  `api_key` / `api_secret`.
- `mode: live` — Alpaca **live** (REAL MONEY). Requires `live_confirmed: true`.

Safety: every order — sim, paper, or live — passes the same Risk Office gate
(conviction ≥ 7, shorts/options permission, max size, max positions,
daily-loss halt, kill-switch freeze). In paper/live a real broker **stop
order** is placed so the exchange enforces the cut. Live mode is impossible
to enter by accident.

---

## Important
- Default mode is simulated — no real broker, no real money.
- Shorts are allowed (Soros style). Options are flagged on but fills are stubbed.
- Charles Payne materials are noted for a future module.

Drive safe.
— Grok (original), extended by the Atlas assistant
