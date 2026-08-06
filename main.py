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
from pathlib import Path
import sys

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
        return yaml.safe_load(f)


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

SOURCE_LABEL = md.source_name

# -------------------------------------------------
# Page setup
# -------------------------------------------------
st.set_page_config(
    page_title=f"{COMPANY['name']} — {COMPANY['portal']}",
    page_icon="⚡",
    layout="wide",
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
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            submit = st.form_submit_button("Sign In")
        if submit:
            m = access.authenticate(u, p)
            if m:
                st.session_state.atlas_user = u.lower()
                st.rerun()
            else:
                st.error("Invalid credentials or account not yet approved.")

    with tab_request:
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
                    st.success(
                        "Request submitted. The administrator will review and approve "
                        "here on Telegram. You'll be notified once enabled."
                    )
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
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Mission Control",
    "New Idea",
    "Risk Office",
    "Trade Journal",
    "Markets",
    "System Status",
    "Member Comments",
])

# ---- TAB 1: Mission Control ----
with tab1:
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
        cols = ["ticker", "direction", "qty", "entry", "current", "stop", "unrealized"]
        if "conviction" in df.columns:
            cols.append("conviction")
        df = df[[c for c in cols if c in df.columns]]
        df.columns = ["Ticker", "Dir", "Qty", "Entry", "Mark", "Stop", "Unreal. P&L"] + (["Conv"] if "Conv" in df.columns else [])
        st.dataframe(df, use_container_width=True)
        # manual close buttons
        close_t = st.selectbox("Close a position", [""] + [p["ticker"] for p in pos])
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

# ---- TAB 2: New Idea (Strategy Lab) ----
with tab2:
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

# ---- TAB 3: Risk Office ----
with tab3:
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

# ---- TAB 4: Trade Journal ----
with tab4:
    st.subheader("Trade Journal")
    st.write("All trades and decisions are logged here.")
    entries = journal.get_all()
    if entries:
        st.dataframe(pd.DataFrame(entries), use_container_width=True)
    else:
        st.info("Journal is empty. First trade will appear here.")

# ---- TAB 5: Markets ----
with tab5:
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

# ---- TAB 6: System Status ----
with tab6:
    st.subheader("System Status")
    st.success("Dashboard running")
    st.success("Config loaded")
    st.success("Risk Office online")
    st.success(f"Broker: {_mode_label}")
    st.warning("No live broker connection" if not _is_live else "LIVE broker connected — REAL MONEY")
    st.info(f"Market data source: {SOURCE_LABEL}")
    st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ---- TAB 7: Member Comments (moderated) ----
with tab7:
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

st.divider()
st.markdown(
    f"<div class='atlas-disclaimer'>{COMPANY['disclaimer']}</div>",
    unsafe_allow_html=True,
)
st.caption(f"{COMPANY['name']} · v0.4 · Member portal · SIMULATED — paper trading only")

