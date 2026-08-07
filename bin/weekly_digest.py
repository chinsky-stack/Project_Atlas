"""ATLAS CAPITAL — Weekly Paper-Trading Digest (educational + practical).

Pulls REAL orders / positions / equity from the Alpaca PAPER account, classifies
each order as ATLAS Auto Trader (our 7-ticker universe) vs unattributed (flagged),
and renders a deep, educational HTML report: what was bought/sold, why (the signal),
and a forward discussion on "how do we make the most money."

Usage:
  GMAIL_ADDRESS=... GMAIL_APP_PASSWORD="..." python bin/weekly_digest.py [--since DAYS]
"""
from __future__ import annotations
import sys, os, json, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

# Our engine's universe (must match config.yaml auto_trader.signal_universe)
ENGINE_UNIVERSE = {"NVDA", "TSLA", "AAPL", "AMD", "META", "COIN", "SPY"}


def load_cfg():
    base = yaml.safe_load(open("config.yaml"))
    loc = yaml.safe_load(open("config.local.yaml"))
    def m(b, o):
        for k, v in o.items():
            if isinstance(v, dict) and isinstance(b.get(k), dict):
                m(b[k], v)
            else:
                b[k] = v
    m(base, loc)
    return base


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build(cfg, since_days=7):
    bc = cfg["broker"]
    t = TradingClient(bc["api_key"], bc["api_secret"], paper=(bc.get("mode") != "live"))
    now = dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(days=since_days)

    orders = t.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.ALL, limit=200))
    # filter to window
    wk = []
    for o in orders:
        sa = o.submitted_at
        if sa.tzinfo is None:
            sa = sa.replace(tzinfo=dt.timezone.utc)
        if sa >= since:
            wk.append(o)
    wk.sort(key=lambda o: o.submitted_at)

    positions = t.get_all_positions()
    ac = t.get_account()
    equity = float(ac.equity)
    bp = float(ac.buying_power)

    # classify
    engine_orders, other_orders = [], []
    for o in wk:
        sym = o.symbol
        if sym in ENGINE_UNIVERSE:
            engine_orders.append(o)
        else:
            other_orders.append(o)

    return {
        "week_start": since, "week_end": now,
        "engine_orders": engine_orders, "other_orders": other_orders,
        "positions": positions, "equity": equity, "bp": bp,
        "cash": float(ac.cash),
    }


def render_html(d):
    # improvement suggestions tracked
    try:
        from src.improvements import all_items
        items = all_items()
    except Exception:
        items = []
    if items:
        imp_rows = "".join(
            f"<tr><td>{esc(i['id'])}</td><td>{esc(i['source'])}</td>"
            f"<td>{esc(i['text'][:120])}</td><td><b>{esc(i['status'])}</b></td>"
            f"<td>{esc(i.get('date','')[:10])}</td></tr>" for i in items)
    else:
        imp_rows = "<tr><td colspan=5>No suggestions logged yet.</td></tr>"

    def fmt_o(o):
        sym = esc(o.symbol)
        side = esc(o.side)
        st = esc(o.status)
        typ = esc(o.type)
        qty = getattr(o, "qty", None) or "?"
        fq = getattr(o, "filled_qty", None) or 0
        sa = o.submitted_at
        if sa.tzinfo is None:
            sa = sa.replace(tzinfo=dt.timezone.utc)
        ts = sa.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        tag = "ATLAS" if o.symbol in ENGINE_UNIVERSE else "OTHER"
        return f"<tr><td>{sym}</td><td>{side}</td><td>{typ}</td><td>{qty}</td><td>{fq}</td><td>{st}</td><td>{ts}</td><td><b>{tag}</b></td></tr>"

    engine_rows = "".join(fmt_o(o) for o in d["engine_orders"]) or "<tr><td colspan=8>No ATLAS Auto Trader orders this week.</td></tr>"
    other_rows = "".join(fmt_o(o) for o in d["other_orders"]) or "<tr><td colspan=8>No unattributed orders.</td></tr>"

    pos_rows = ""
    for p in d["positions"]:
        pos_rows += f"<tr><td>{esc(p.symbol)}</td><td>{esc(p.qty)}</td><td>{esc(p.avg_entry_price)}</td><td>{esc(p.market_value)}</td><td>{esc(p.unrealized_pl)}</td></tr>"
    pos_rows = pos_rows or "<tr><td colspan=5>No open positions.</td></tr>"

    other_flag = ""
    if d["other_orders"]:
        other_flag = f"""<div style="border:1px solid #c0392b;background:#fdecea;padding:10px;border-radius:6px;margin:10px 0">
          <b>⚠ Unattributed orders detected.</b> {len(d['other_orders'])} order(s) this week were placed by something
          OTHER than the ATLAS Auto Trader (symbols outside our 7-ticker universe, or submitted outside market hours).
          These are NOT part of our strategy and should be investigated before trusting any P&amp;L.
        </div>"""

    html = f"""
    <html><body style="font-family:-apple-system,Segoe UI,Arial;color:#222;max-width:820px;margin:auto">
    <h2 style="color:#0b3d91">ATLAS CAPITAL — Weekly Paper-Trading Digest</h2>
    <p style="color:#666">Week of {d['week_start'].strftime('%b %d')} – {d['week_end'].strftime('%b %d, %Y')} · PAPER ONLY · educational</p>
    <div style="background:#f4f6fb;border-left:4px solid #0b3d91;padding:10px 14px;border-radius:6px">
      <b>Account snapshot:</b> Equity ${d['equity']:,.0f} · Cash ${d['cash']:,.0f} · Buying power ${d['bp']:,.0f}
    </div>
    {other_flag}
    <h3>1. What the ATLAS Auto Trader did</h3>
    <p>Every order below was generated by our rules-based engine (momentum + trend + mean-reversion on daily bars,
    conviction ≥ 8, capped by the Risk Office). Stocks/shorts and defined-risk option verticals only.</p>
    <table border=1 cellpadding=6 cellspacing=0 style="border-collapse:collapse;width:100%;font-size:13px">
      <tr style="background:#0b3d91;color:#fff"><th>Symbol</th><th>Side</th><th>Type</th><th>Qty</th><th>Filled</th><th>Status</th><th>Time</th><th>Src</th></tr>
      {engine_rows}
    </table>
    <h3>2. Positions currently open</h3>
    <table border=1 cellpadding=6 cellspacing=0 style="border-collapse:collapse;width:100%;font-size:13px">
      <tr style="background:#0b3d91;color:#fff"><th>Symbol</th><th>Qty</th><th>Avg entry</th><th>Mkt value</th><th>Unrealized P&amp;L</th></tr>
      {pos_rows}
    </table>
    <h3>3. Why — the educational part</h3>
    <p>Our signal logic (transparent, not a black box):</p>
    <ul>
      <li><b>Momentum:</b> 20-day return &gt; +6% with an uptrend → long; &lt; −6% with downtrend → short.</li>
      <li><b>Trend:</b> price above its 50-day average confirms direction.</li>
      <li><b>Mean-reversion:</b> a pullback inside an uptrend (5-day dip) can trigger a high-conviction long.</li>
      <li><b>Sizing:</b> each position capped at 20% of book; total risk ≤ 40%; options premium ≤ 8% per trade;
      kill-switch freezes everything at 35% drawdown.</li>
      <li><b>Options:</b> only defined-risk vertical spreads (bull-call / bear-put) — never naked shorts.</li>
    </ul>
    <p>For each filled order above, the <i>why</i> is the signal that fired for that ticker at that time. We are learning
    which regimes (trending vs choppy) our rules capture and which they whipsaw on.</p>
    <h3>4. Orders NOT from our strategy (flagged for review)</h3>
    <table border=1 cellpadding=6 cellspacing=0 style="border-collapse:collapse;width:100%;font-size:13px">
      <tr style="background:#c0392b;color:#fff"><th>Symbol</th><th>Side</th><th>Type</th><th>Qty</th><th>Filled</th><th>Status</th><th>Time</th><th>Src</th></tr>
      {other_rows}
    </table>
    <h3>5. Discussion — how do we make the most money (responsibly)?</h3>
    <p>This is the honest, evolving view. The goal is compounding, not any single trade. Levers we can tune:</p>
    <ul>
      <li><b>Regime detection:</b> pause trend-following in choppy/low-volatility markets; our current rules get whipsawed. Add a volatility filter.</li>
      <li><b>Options rotary:</b> selling premium (credit spreads / iron condors) in high-IV names can monetize time decay — but only defined-risk.</li>
      <li><b>Concentration vs breadth:</b> fewer, higher-conviction names (our 7) vs expanding the universe. Breadth reduces idiosyncratic blowups.</li>
      <li><b>Reinvest discipline:</b> profits compound into the book up to a ceiling; we must resist loosening caps after a win streak.</li>
      <li><b>Costs &amp; slippage:</b> paper ignores them; live won't. Any live plan must haircut returns for fees.</li>
    </ul>
    <p><b>Bottom line:</b> the engine is a disciplined apprentice, not a Oracle. It will take losers. What compounds is the
    <i>system</i> — risk-first, evidence-driven, never over-levered. We review, we tighten, we repeat.</p>
    <p style="background:#eef;padding:8px;border-radius:6px"><b>Questions? Talk to Hermes.</b> Email Dr. King and start your message with
    <b>"Hermes:"</b> — Hermes (the ATLAS assistant, named for the brand Penn likes) reads inbound mail and answers your
    questions right away. <b>Ask about:</b> your login/password, how the options spreads work, what's paper vs live,
    where to see performance, or anything in this digest. <b>What to expect:</b> Hermes answers questions conversationally —
    it will NOT change your account or place trades from email. For account changes, Dr. King handles those.</p>
    <hr>
    <h3>6. Improvement suggestions tracked</h3>
    <table border=1 cellpadding=6 cellspacing=0 style="border-collapse:collapse;width:100%;font-size:13px">
      <tr style="background:#0b3d91;color:#fff"><th>ID</th><th>Source</th><th>Suggestion</th><th>Status</th><th>Date</th></tr>
      {imp_rows}
    </table>
    <hr>
    <p style="color:#888;font-size:12px">ATLAS CAPITAL · paper-trading research only · not investment advice ·
    generated {d['week_end'].strftime('%Y-%m-%d %H:%M')} UTC</p>
    </body></html>
    """
    return html


def main():
    cfg = load_cfg()
    mail = cfg.get("mail", {})
    # creds from gitignored config.local.yaml (preferred); env overrides
    os.environ.setdefault("GMAIL_ADDRESS", mail.get("gmail_address", ""))
    os.environ.setdefault("GMAIL_APP_PASSWORD", mail.get("gmail_app_password", ""))
    to_addr = os.getenv("DIGEST_TO", mail.get("digest_to", "pennmou@gmail.com"))
    cc_addr = os.getenv("DIGEST_CC", mail.get("digest_cc", "ilyatorchinsky@gmail.com"))
    bcc_addr = os.getenv("DIGEST_BCC", "")
    since_days = int(sys.argv[sys.argv.index("--since") + 1]) if "--since" in sys.argv else 7
    d = build(cfg, since_days)
    html = render_html(d)
    subject = f"ATLAS CAPITAL Weekly Digest — {d['week_end'].strftime('%b %d, %Y')} (PAPER)"
    from bin.mailer import send_email
    send_email(subject, html, to_addr, cc_addr=cc_addr, bcc_addr=bcc_addr)
    # also write a local copy for the record
    os.makedirs("data/digests", exist_ok=True)
    fn = f"data/digests/{d['week_end'].strftime('%Y-%m-%d')}.html"
    open(fn, "w").write(html)
    print("Saved local copy:", fn)


if __name__ == "__main__":
    main()
