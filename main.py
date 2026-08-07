"""
Project Atlas — Mission Control Dashboard
Simple Streamlit app. Non-coder friendly.

v0.3 — SIMULATED LIVE MODE
  * Live (or simulated) market data via src/market_data.py
  * Paper execution engine via src/paper_trader.py that enforces the
    Risk Office rules in code (conviction gate, position limits, auto
    stop-cut, daily-loss halt, kill-switch freeze).
  * NO broker. NO real money. Simulated fills only.
"""

import streamlit as st
import yaml
import pandas as pd
from datetime import datetime
import json, os, secrets, string
from pathlib import Path
import sys

# Portal version — bump on any user-visible change so cache staleness is obvious.
# Tracked in CHANGELOG.md.
VERSION = "0.5"

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from risk_office import RiskOffice
from journal import TradeJournal
from strategy_lab import StrategyLab
from market_data import MarketData
from paper_trader import PaperTrader
from broker import get_broker
from access import AccessStore
from branding import COMPANY, COLORS, LOGIN_CSS

# -------------------------------------------------
# Load config
# -------------------------------------------------
CONFIG_PATH = Path(__file__).parent / "config.yaml"


@st.cache_data
def load_config():
    with open(CONFIG_PATH, "r") as f:
        cfg = yaml.safe_load(f)
    # Merge local overrides (gitignored, holds real broker keys). Local wins.
    local = CONFIG_PATH.parent / "config.local.yaml"
    if local.exists():
        try:
            with open(local) as lf:
                loc = yaml.safe_load(lf) or {}
            _deep_merge(cfg, loc)
        except Exception:
            pass
    return cfg


def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


config = load_config()


# -------------------------------------------------
# Engine singletons (persist across reruns in session)
# -------------------------------------------------
@st.cache_resource
def get_market():
    return MarketData(config)


@st.cache_resource
def get_trader():
    return PaperTrader(config, get_market())


@st.cache_resource
def get_broker_obj():
    return get_broker(config, get_market(), get_trader())


@st.cache_resource
def get_journal():
    return TradeJournal()


@st.cache_resource
def get_lab():
    return StrategyLab()


md = get_market()
trader = get_trader()          # in-process sim engine (used by SimBroker)
broker = get_broker_obj()      # uniform broker interface (sim / alpaca paper / live)
journal = get_journal()
lab = get_lab()
cfg = load_config()            # full merged config (config.yaml + config.local.yaml)


def _gen_temp_pw(n=10):
    """Generate a reasonable temporary password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _alert_admin(text):
    """Record an important alert for the relay cron to deliver to Telegram.
    Silent in routine scans; only surfaces here when something needs Dr. King's eye."""
    try:
        os.makedirs("data", exist_ok=True)
        with open("data/.alerts_pending.jsonl", "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "kind": "admin_alert",
                "text": text,
            }) + "\n")
    except Exception:
        pass


SOURCE_LABEL = md.source_name

# -------------------------------------------------
# Page setup
# -------------------------------------------------
st.set_page_config(
    page_title=f"{COMPANY['name']} — {COMPANY['portal']}",
    page_icon="⚡",
    layout="wide",
    # Hide Streamlit's hamburger menu + "Made with Streamlit" footer so the
    # branded ATLAS header owns the top bar (no Light/Dark/Print leak).
    menu_items={},
)

# Apply brand styling
st.markdown(LOGIN_CSS, unsafe_allow_html=True)

# -------------------------------------------------
# Access control (per-user, approval-gated, moderated comments)
# -------------------------------------------------
ACCESS_CFG = config.get("access", {})
MAX_MEMBERS = int(ACCESS_CFG.get("max_members", 6))
access = AccessStore(max_members=MAX_MEMBERS)


def atlas_brand_header(subtitle: str = ""):
    st.markdown(
        f"""
        <div class="atlas-brand">
          <div class="atlas-logo">⚡</div>
          <div>
            <div class="atlas-name">{COMPANY['name']}</div>
            <div class="atlas-sub">{COMPANY['portal']}{(' · ' + subtitle) if subtitle else ''}</div>
          </div>
        </div>
        <div class="atlas-divider"></div>
        """,
        unsafe_allow_html=True,
    )


# Initialise session auth state
for k in ("atlas_user", "atlas_auth_pending"):
    if k not in st.session_state:
        st.session_state[k] = "" if k == "atlas_user" else False

# ---------------- Not authenticated: branded gate ----------------
if not st.session_state.atlas_user:
    atlas_brand_header("Secure Access")
    st.markdown(
        f"<div class='atlas-muted' style='margin-bottom:10px'>{COMPANY['contact']}</div>",
        unsafe_allow_html=True,
    )

    tab_login, tab_request = st.tabs(["Member Sign-In", "Request Access"])

    with tab_login:
        with st.form("login_form"):
            u = st.text_input("Username", autocomplete="username")
            p = st.text_input("Password", type="password", autocomplete="current-password")
            submit = st.form_submit_button("Sign In")
        if submit:
            try:
                ip = str(st.context.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                         or st.context.headers.get("X-Real-IP", "")
                         or st.context.client.request.remote_addr or "unknown")
            except Exception:
                ip = "unknown"
            m = access.authenticate(u, p, ip=ip)
            if m:
                st.session_state.atlas_user = u.lower()
                st.rerun()
            else:
                st.error("Invalid credentials or account not yet approved.")
        # Self-service password reset for ALREADY-APPROVED members.
        # No admin approval needed — but Dr. King is notified. Lightweight email
        # check prevents a random person from resetting someone else's password.
        st.divider()
        with st.form("pw_reset_form"):
            ru = st.text_input("Username")
            remail = st.text_input("Your email on file")
            rreset = st.form_submit_button("Reset my password")
        if rreset:
            uname = ru.strip().lower()
            if not uname or not remail:
                st.error("Username and the email on file are required.")
            elif not access.is_approved(uname):
                st.error("Account not found or not approved.")
                # notify admin of a suspicious attempt
                _alert_admin(f"⚠ Password-reset attempt for unapproved/unknown user '{uname}' from {ip}")
            else:
                stored_email = access.member_email(uname)
                if stored_email and stored_email.lower() != remail.strip().lower():
                    st.error("Email does not match our records.")
                    _alert_admin(f"⚠ Password-reset email mismatch for '{uname}' (got {remail}) from {ip}")
                else:
                    new_pw = _gen_temp_pw()
                    try:
                        access.reset_password(uname, new_pw)
                        st.success(f"Password reset. Your new temporary password is:\n\n**{new_pw}**\n\nPlease sign in and change it under Account.")
                        # email it if we have an address
                        if stored_email:
                            try:
                                from bin.mailer import send_email
                                mail_cfg = cfg.get("mail", {})
                                os.environ.setdefault("GMAIL_ADDRESS", mail_cfg.get("gmail_address", ""))
                                os.environ.setdefault("GMAIL_APP_PASSWORD", mail_cfg.get("gmail_app_password", ""))
                                send_email("ATLAS CAPITAL — your password was reset",
                                           f"<p>Hi {uname},</p><p>Your ATLAS CAPITAL password was reset via the self-service portal. "
                                           f"Your new temporary password is: <b>{new_pw}</b></p>"
                                           f"<p>Sign in and change it under the Account tab.</p>",
                                           stored_email)
                            except Exception:
                                pass
                        _alert_admin(f"🔑 Self-service password reset: '{uname}' reset their own password.")
                    except Exception as e:
                        st.error(f"Reset failed: {e}")

    with tab_request:
        # After a successful submit we swap the form for a clean confirmation
        # (and the form fields clear on the next render).
        if st.session_state.get("request_submitted"):
            st.success(
                "Request submitted — you'll hear back from the administrator."
            )
            if st.button("Submit another request"):
                st.session_state.request_submitted = False
                st.rerun()
        else:
            with st.form("request_form"):
                ru = st.text_input("Choose a username")
                rp = st.text_input("Create a password", type="password")
                remail = st.text_input("Email (optional)")
                rnote = st.text_area("Why do you want access? (optional)")
                rsubmit = st.form_submit_button("Submit Request")
            if rsubmit:
                if not ru or not rp:
                    st.error("Username and password are required.")
                else:
                    try:
                        access.request_access(ru, rp, remail, rnote)
                        st.session_state.request_submitted = True
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    st.markdown(
        f"<div class='atlas-disclaimer'>{COMPANY['disclaimer']}</div>",
        unsafe_allow_html=True,
    )
    st.stop()


# Prominent SIMULATED banner
_mode_label = broker.label
_is_live = getattr(broker, "is_live", False)
_banner_color = "error" if _is_live else "warning"
_msg = (
    f"⚠️ **{_mode_label}** — "
    + ("REAL MONEY at risk. Every order passes the Risk Office gate." if _is_live
       else "No real money moves. Prices: **%s**. Fills are simulated; risk rules enforced in code." % SOURCE_LABEL)
    + f"  ·  v{VERSION}"
)
if _banner_color == "error":
    st.error(_msg)
else:
    st.warning(_msg)

atlas_brand_header("Mission Control")
# signed-in chip + logout
scol1, scol2 = st.columns([6, 1])
with scol1:
    st.markdown(
        f"<span style='color:{COLORS['muted']};font-size:13px'>Signed in as "
        f"<b style='color:{COLORS['accent']}'>{st.session_state.atlas_user}</b></span>",
        unsafe_allow_html=True,
    )
with scol2:
    if st.button("Sign Out", key="logout"):
        st.session_state.atlas_user = ""
        st.rerun()

# -------------------------------------------------
# Sidebar — Account & Risk Snapshot
# -------------------------------------------------
m = broker.metrics()
with st.sidebar:
    st.header("Account")
    st.metric("Equity", f"${m['equity']:,.2f}")
    st.metric("Cash", f"${m['cash']:,.2f}")
    st.metric("Unrealized P&L", f"${m['unrealized']:,.2f}")
    st.metric("Mode", _mode_label)
    st.caption(f"Prices: {SOURCE_LABEL}")
    st.caption(f"Member: {st.session_state.atlas_user}")

    st.header("Risk Rules (Soros-adapted)")
    risk = config["risk"]
    st.write(f"Max risk / trade: **{risk['max_risk_per_trade_pct']}%**")
    st.write(f"Max daily loss: **{risk['max_daily_loss_pct']}%**")
    st.write(f"Kill switch: **{risk['kill_switch_drawdown_pct']}%**")
    st.write(f"Max position size: **{risk['max_position_pct']}%**")
    st.write(f"Open positions: **{m['open_count']}/{risk['max_open_positions']}**")
    st.write(f"Shorts: {'✅ ON' if risk['allow_shorts'] else '❌ OFF'}")
    st.write(f"Options: {'✅ ON' if risk['allow_options'] else '❌ OFF'}")

    st.divider()
    if broker.state.killswitch:
        st.error("🛑 KILL-SWITCH ARMED — trading frozen.")
        if st.button("Reset Kill-Switch (post-mortem done)"):
            broker.reset_killswitch()
            st.rerun()
    st.caption("Edit config.yaml to change these numbers")

# -------------------------------------------------
# Tabs
# -------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "Auto Trader",
    "Mission Control",
    "New Idea",
    "Risk Office",
    "Trade Journal",
    "Markets",
    "System Status",
    "Member Comments",
    "Account",
])

# ---- TAB 2: Mission Control ----
with tab2:
    st.subheader("Today's One Objective")
    objective = st.text_input(
        "What is the single most important thing to do today?",
        placeholder="e.g. Paper trade the first high-conviction idea",
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Open Positions", f"{m['open_count']}")
    with col2:
        st.metric("Equity", f"${m['equity']:,.2f}")
    with col3:
        st.metric("Drawdown from Peak", f"{m['drawdown_pct']:.1f}%")

    st.divider()
    st.subheader("Open Book (marked to live prices)")
    pos = broker.get_positions()
    if pos:
        df = pd.DataFrame(pos)
        pretty = {
            "ticker": "Ticker", "direction": "Dir", "qty": "Qty", "entry": "Entry",
            "current": "Mark", "stop": "Stop", "unrealized": "Unreal. P&L",
            "conviction": "Conv",
        }
        df = df[[c for c in pretty if c in df.columns]]
        df = df.rename(columns=pretty)
        st.dataframe(df, use_container_width=True)
        # manual close buttons
        close_t = st.selectbox("Close a position", ["" ] + [p["ticker"] for p in pos])
        if close_t and st.button("Close selected"):
            res = broker.close_position(close_t)
            st.info(res.message)
            st.rerun()
    else:
        st.info("No open positions. Submit a high-conviction idea in the 'New Idea' tab.")

    st.divider()
    st.subheader("Quick Checklist")
    checks = [
        "Review dashboard",
        "Check news / economic calendar",
        "Verify data feeds",
        "Choose one priority task",
        "Complete the task",
        "Document & journal",
    ]
    for c in checks:
        st.checkbox(c)

    if st.button("Evaluate stops now (auto-cut losers)"):
        events = broker.evaluate_stops()
        for e in events:
            st.warning(e)
        if not events:
            st.success("No stops triggered (broker-enforced stops apply in paper/live mode).")
        st.rerun()

# ---- TAB 3: New Idea (Strategy Lab) ----
with tab3:
    st.subheader("New High-Conviction Idea")
    st.caption("Soros style: only proceed if conviction is high. Submitting routes to the Risk Office + simulated fill.")

    with st.form("new_idea_form"):
        ticker = st.text_input("Ticker / Instrument", placeholder="e.g. SQQQ, AAPL, TSLA")
        direction = st.selectbox("Direction", ["Long", "Short", "Call", "Put", "Other"])
        thesis = st.text_area("Thesis (why this works)", height=100)
        edge_source = st.selectbox(
            "Source of Edge (required)",
            ["", "Behavioral", "Structural", "Informational", "Risk Premium", "Constraint-based", "None / Unknown"],
        )
        who_loses = st.text_input("Who is on the other side and why are they willing to lose?")
        conviction = st.slider("Conviction (1-10)", 1, 10, 7)
        horizon = st.selectbox("Time horizon", ["Intraday", "1-5 days", "1-4 weeks", "1-3 months", "Longer"])
        stop = st.number_input("Stop / Invalidation price", value=0.0, step=0.5, min_value=0.0)

        submitted = st.form_submit_button("Submit Idea → Risk Office → Sim Fill")

        if submitted:
            if not ticker or not thesis or edge_source in ["", "None / Unknown"]:
                st.error("Ticker, thesis, and a real edge source are required. Idea rejected.")
            elif conviction < 7:
                st.warning("Conviction below 7. Under Soros rules this is automatic NO-ACTION.")
            elif direction not in ["Long", "Short"]:
                st.warning("Options flow (Call/Put/Other) is stubbed — only Long/Short simulate fills yet.")
            elif stop <= 0:
                st.warning("Set a stop / invalidation price before risking capital.")
            else:
                # Route through Risk Office + broker (sim / alpaca paper / live)
                res = broker.submit_order(ticker, direction, conviction, stop)
                if res.ok:
                    st.success(res.message)
                    st.info("Risk Office approved. " + ("Simulated fill recorded." if not _is_live else "Order + broker stop submitted."))
                    if res.position:
                        journal.add_entry({
                            "type": "open",
                            "ticker": res.position["ticker"],
                            "direction": res.position["direction"],
                            "qty": res.position["qty"],
                            "entry": res.position["entry"],
                            "stop": res.position["stop"],
                            "conviction": conviction,
                            "thesis": thesis,
                            "edge_source": edge_source,
                        })
                else:
                    st.error(res.message)
                st.rerun()

    st.divider()
    st.subheader("Idea Pipeline (persisted)")
    ideas = lab.get_all()
    if ideas:
        st.dataframe(pd.DataFrame(ideas), use_container_width=True)
    else:
        st.info("No ideas submitted yet.")

# ---- TAB 4: Risk Office ----
with tab4:
    st.subheader("Risk Office")
    st.caption("Hard gate. Can veto any idea. Rules are enforced in code at order time.")

    ro = RiskOffice(config)
    st.write("Current risk parameters loaded from config.yaml")
    st.json(config["risk"])

    st.divider()
    st.subheader("Position Sizing Calculator")
    col_a, col_b = st.columns(2)
    with col_a:
        equity = st.number_input("Current equity ($)", value=float(m["equity"]), step=50.0)
        risk_pct = st.number_input("Risk % for this trade", value=8.0, step=0.5)
    with col_b:
        entry = st.number_input("Entry price", value=100.0, step=0.5)
        stop = st.number_input("Stop / Invalidation price", value=95.0, step=0.5)

    if entry != stop:
        risk_dollars = equity * (risk_pct / 100)
        risk_per_share = abs(entry - stop)
        shares = int(risk_dollars / risk_per_share) if risk_per_share > 0 else 0
        position_value = shares * entry
        position_pct = (position_value / equity) * 100 if equity > 0 else 0

        st.metric("Shares / Contracts", f"{shares}")
        st.metric("Position Value", f"${position_value:,.0f}")
        st.metric("% of Equity", f"{position_pct:.1f}%")

        if position_pct > config["risk"]["max_position_pct"]:
            st.error(f"Position exceeds max allowed ({config['risk']['max_position_pct']}%). Reduce size.")
        else:
            st.success("Size is within limits.")

    st.divider()
    st.subheader("Live Engine Guards")
    st.write(f"Daily loss used: **{m['daily_loss_pct']:.2f}%** (halt at {risk['max_daily_loss_pct']}%)")
    st.write(f"Drawdown used: **{m['drawdown_pct']:.2f}%** (kill-switch at {risk['kill_switch_drawdown_pct']}%)")
    st.write(f"Kill-switch armed: **{'YES' if broker.state.killswitch else 'no'}**")
    if st.button("Reset whole simulated book to starting capital"):
        broker.reset()
        st.success("Book reset.")
        st.rerun()

# ---- TAB 5: Trade Journal ----
with tab5:
    st.subheader("Trade Journal")
    st.write("All trades and decisions are logged here.")
    entries = journal.get_all()
    if entries:
        st.dataframe(pd.DataFrame(entries), use_container_width=True)
    else:
        st.info("Journal is empty. First trade will appear here.")

# ---- TAB 6: Markets ----
with tab6:
    st.subheader("Markets (live / simulated quotes)")
    st.caption(f"Source: {SOURCE_LABEL}. Quote latency depends on the feed.")
    tickers = st.text_input(
        "Tickers (comma separated)",
        value="AAPL,TSLA,NVDA,SPY,QQQ",
    ).upper()
    if st.button("Refresh quotes"):
        pass
    symbols = [t.strip() for t in tickers.split(",") if t.strip()]
    rows = []
    for t in symbols:
        q = md.quote(t)
        chg = ((q.price - q.prev_close) / q.prev_close * 100) if q.prev_close else 0.0
        rows.append({
            "Ticker": t,
            "Price": round(q.price, 2),
            "Chg %": round(chg, 2),
            "Source": q.source,
            "Time": q.ts.strftime("%H:%M:%S"),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("Enter at least one ticker.")

# ---- TAB 7: System Status ----
with tab7:
    st.subheader("System Status")
    st.success("Dashboard running")
    st.success("Config loaded")
    st.success("Risk Office online")
    st.success(f"Broker: {_mode_label}")
    st.warning("No live broker connection" if not _is_live else "LIVE broker connected — REAL MONEY")
    st.info(f"Market data source: {SOURCE_LABEL}")
    st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ---- TAB 8: Member Comments (moderated) ----
with tab8:
    st.subheader("Member Comments")
    st.caption("Submitted comments are reviewed by the administrator before they appear. "
               "This keeps the portal clean and intentional.")
    with st.form("comment_form"):
        ctext = st.text_area("Share a comment or feedback", height=100)
        csubmit = st.form_submit_button("Submit Comment")
    if csubmit:
        try:
            access.add_comment(st.session_state.atlas_user, ctext)
            st.success("Comment submitted. It will appear once the administrator approves it.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    st.divider()
    st.markdown(f"<div class='atlas-sub' style='font-size:11px'>Approved comments</div>", unsafe_allow_html=True)
    vis = access.visible_comments()
    if vis:
        for c in vis:
            st.markdown(
                f"<div class='atlas-card' style='margin-bottom:10px'>"
                f"<div style='color:{COLORS['accent']};font-weight:700'>{c['user']}</div>"
                f"<div style='color:{COLORS['text']}'>{c['text']}</div>"
                f"<div class='atlas-muted'>{c['created']}</div></div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("No approved comments yet.")

    # ---- Improvement suggestions (read-only, visible to all members) ----
    st.divider()
    st.markdown(f"<div class='atlas-sub' style='font-size:11px'>Improvement suggestions</div>", unsafe_allow_html=True)
    st.caption("Ideas from members and Dr. King. Everyone can see what's been proposed and its status. "
               "Dr. King reviews and acts on them.")
    try:
        from src.improvements import all_items as _all_sugg
        sugg = _all_sugg()
    except Exception:
        sugg = []
    if sugg:
        srows = "".join(
            f"<tr><td style='padding:4px 8px'>{s['id']}</td>"
            f"<td style='padding:4px 8px'>{s['source']}</td>"
            f"<td style='padding:4px 8px'>{s['text'][:160]}</td>"
            f"<td style='padding:4px 8px'><b>{s['status']}</b></td>"
            f"<td style='padding:4px 8px'>{s.get('date','')[:10]}</td></tr>"
            for s in sugg)
        st.markdown(
            f"<table style='width:100%;border-collapse:collapse;font-size:13px;color:{COLORS['text']}'>"
            f"<tr style='background:{COLORS['panel']}'>"
            f"<th style='padding:4px 8px;text-align:left'>ID</th><th style='padding:4px 8px;text-align:left'>Source</th>"
            f"<th style='padding:4px 8px;text-align:left'>Suggestion</th><th style='padding:4px 8px;text-align:left'>Status</th>"
            f"<th style='padding:4px 8px;text-align:left'>Date</th></tr>{srows}</table>",
            unsafe_allow_html=True,
        )
    else:
        st.info("No suggestions logged yet.")

# ---- TAB 9: Account (self-service password change) ----
with tab9:
    st.subheader("Account")
    st.markdown(
        f"<span style='color:{COLORS['muted']}'>Signed in as "
        f"<b style='color:{COLORS['accent']}'>{st.session_state.atlas_user}</b></span>",
        unsafe_allow_html=True,
    )
    st.divider()
    st.write("Change your password")
    with st.form("change_pw_form"):
        cur = st.text_input("Current password", type="password")
        new1 = st.text_input("New password", type="password")
        new2 = st.text_input("Confirm new password", type="password")
        cp_submit = st.form_submit_button("Update Password")
    if cp_submit:
        if not cur or not new1 or not new2:
            st.error("All fields are required.")
        elif new1 != new2:
            st.error("New passwords do not match.")
        elif len(new1) < 4:
            st.error("New password must be at least 4 characters.")
        elif not access.authenticate(st.session_state.atlas_user, cur):
            st.error("Current password is incorrect.")
        else:
            try:
                access.reset_password(st.session_state.atlas_user, new1)
                st.success("Password updated. Use it next time you sign in.")
            except ValueError as e:
                st.error(str(e))

    st.divider()
    if st.button("Sign Out", key="logout2"):
        st.session_state.atlas_user = ""
        st.rerun()

# ---- TAB 1: Auto Trader (Soros-adapted, aggressive but HARD-CAPPED, PAPER ONLY) ----
with tab1:
    st.subheader("Autonomous Trader")
    st.warning("⚠️ PAPER ONLY. This engine trades the Alpaca PAPER sandbox — no real money. "
               "Every order passes the Risk Office + kill-switch. Limits are set in config.yaml → auto_trader.")
    at_cfg = cfg.get("auto_trader", {})
    if not at_cfg.get("paper_only", True):
        st.error("auto_trader.paper_only is false — engine refuses to run (safety).")
    else:
        # build/persist the engine in session state
        if "at_engine" not in st.session_state:
            st.session_state.at_engine = None
        if st.session_state.at_engine is None:
            try:
                from auto_trader import AutoTrader
                st.session_state.at_engine = AutoTrader(broker, cfg, market_price=broker.market_price)
                # Autonomous launch: if authorized + paper-only, start on first load
                if at_cfg.get("auto_start", False) and at_cfg.get("paper_only", True):
                    try:
                        st.session_state.at_engine.start()
                    except Exception as e:
                        st.warning(f"AutoTrader auto-start skipped: {e}")
            except Exception as e:
                st.error(f"Engine init failed: {e}")
        eng = st.session_state.at_engine
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("▶ Start", key="at_start"):
                if eng and eng.start():
                    st.success("AutoTrader started (PAPER).")
                else:
                    st.error("Could not start (already running, kill-switch, or not paper_only).")
                st.rerun()
        with c2:
            if st.button("■ Stop", key="at_stop"):
                if eng:
                    eng.stop()
                st.info("Stopped.")
                st.rerun()
        with c3:
            if st.button("↺ Reset Kill-Switch", key="at_reset"):
                if eng:
                    eng.reset_killswitch()
                st.rerun()
        if eng:
            s = eng.status()
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Book", f"${s['book']:,.0f}")
            m2.metric("Drawdown", f"{s['drawdown_pct']:.1f}%")
            m3.metric("Positions", s["positions"])
            m4.metric("Realized P&L", f"${s['realized_pnl']:,.0f}")
            st.caption(f"Running: {s['running']} · Kill-switch: {s['killswitch']} · Daily loss: {s['daily_loss']:.1f}%")
            st.divider()
            st.write("**Last signals**")
            for sig in s["last_signals"]:
                st.caption(f"{sig['ticker']}: {sig['direction']} (conv {sig['conviction']}) — {sig['rationale']}")
            st.divider()
            st.write("**Engine log**")
            for line in s["log"]:
                st.caption(line)

    # ---- Both books (read-only observation) ----
    st.divider()
    st.markdown(f"<div class='atlas-sub' style='font-size:11px'>Account Books — read-only</div>", unsafe_allow_html=True)
    st.caption("Two separate paper accounts under ATLAS CAPITAL. Dr. King's is traded automatically by Hermes; "
               "Penn's (MASTA) is traded by Penn himself. Both are shown here for visibility. Updates on page refresh.")

    # Dr. King's book (the auto-traded one) via the live broker client
    st.write("**Dr. King's Book — auto-traded by Hermes (paper)**")
    try:
        ac = broker.trading.get_account()
        dk_pos = broker.trading.get_all_positions()
        dk1, dk2, dk3 = st.columns(3)
        dk1.metric("Equity", f"${float(ac.equity):,.0f}")
        dk2.metric("Cash", f"${float(ac.cash):,.0f}")
        dk3.metric("Buying Power", f"${float(ac.buying_power):,.0f}")
        if dk_pos:
            for p in dk_pos:
                st.caption(f"{p.symbol}: {p.qty} @ {p.avg_entry_price} — MV ${float(p.market_value):,.0f} · uPL ${float(p.unrealized_pl):,.0f}")
        else:
            st.caption("No open positions.")
    except Exception as e:
        st.warning(f"Could not load Dr. King's book: {e}")

    # Penn's book (MASTA) — read-only via member_broker
    st.write("**Penn's Book (MASTA) — traded by Penn himself**")
    try:
        from src.member_broker import snapshot as penn_snap
        ps = penn_snap(cfg, "penn", since_days=7)
        if ps is None:
            st.info("Penn's account keys not configured yet (config.local.yaml → members.penn.broker).")
        else:
            pm1, pm2, pm3 = st.columns(3)
            pm1.metric("Equity", f"${ps['equity']:,.0f}")
            pm2.metric("Cash", f"${ps['cash']:,.0f}")
            pm3.metric("Buying Power", f"${ps['bp']:,.0f}")
            if ps["positions"]:
                for p in ps["positions"]:
                    st.caption(f"{p.symbol}: {p.qty} @ {p.avg_entry_price} — MV ${float(p.market_value):,.0f} · uPL ${float(p.unrealized_pl):,.0f}")
            else:
                st.caption("No open positions.")
            if ps["orders"]:
                st.write("**Recent orders (7d)**")
                for o in ps["orders"][-15:]:
                    st.caption(f"{o.symbol} {o.side} {o.type} {o.status} @ {o.submitted_at}")
    except Exception as e:
        st.warning(f"Could not load Penn's book: {e}")

st.divider()
st.markdown(
    f"<div class='atlas-disclaimer'>{COMPANY['disclaimer']}</div>",
    unsafe_allow_html=True,
)
st.caption(f"{COMPANY['name']} · v{VERSION} · Member portal · SIMULATED — paper trading only")

