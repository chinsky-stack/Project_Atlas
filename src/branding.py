"""
Branding for the Atlas member portal — a legit, polished company identity.

We present Project Atlas as "ATLAS CAPITAL — Member Research Portal" so
friends see a professional, intentional product rather than a hobby script.
All copy is honest: it's a research/simulation portal, not a registered
investment adviser. Disclosures are included where needed.
"""

COMPANY = {
    "name": "ATLAS CAPITAL",
    "portal": "Member Research Portal",
    "tagline": "Soros-style high-conviction research, simulated.",
    "disclaimer": (
        "ATLAS CAPITAL is a private research and simulation environment. "
        "Nothing here is investment advice or a solicitation. All trading shown is "
        "simulated unless a live broker is explicitly enabled by the administrator. "
        "Markets involve risk; simulated results do not predict live outcomes."
    ),
    "contact": "Access is by invitation only. Requests are reviewed by the administrator.",
}

# Brand palette (dark, institutional)
COLORS = {
    "bg": "#0b0f17",
    "panel": "#121826",
    "accent": "#d4af37",      # gold
    "accent2": "#3b82f6",     # blue
    "text": "#e6e9ef",
    "muted": "#8b94a7",
    "ok": "#22c55e",
    "warn": "#f59e0b",
    "err": "#ef4444",
}

LOGIN_CSS = f"""
<style>
/* ---- ATLAS CAPITAL branded shell ---- */
html, body, .stApp {{
    background: {COLORS['bg']} !important;
    color: {COLORS['text']} !important;
}}
[data-testid="stAppViewContainer"] > section {{
    background: {COLORS['bg']} !important;
}}
.block-container {{ max-width: 1100px; padding-top: 2rem; }}

/* Brand header */
.atlas-brand {{
    display:flex; align-items:center; gap:14px; margin-bottom:6px;
}}
.atlas-logo {{
    width:46px;height:46px;border-radius:10px;
    background: linear-gradient(135deg, {COLORS['accent']}, #b8860b);
    display:flex;align-items:center;justify-content:center;
    font-weight:800;font-size:22px;color:#0b0f17;box-shadow:0 4px 14px rgba(212,175,55,.25);
}}
.atlas-name {{ font-size:20px; font-weight:800; letter-spacing:.5px; color:{COLORS['text']}; }}
.atlas-sub {{ font-size:12px; color:{COLORS['muted']}; letter-spacing:2px; text-transform:uppercase; }}
.atlas-divider {{ height:1px; background:linear-gradient(90deg,{COLORS['accent']},transparent); margin:14px 0 18px; }}

/* Cards / panels */
.atlas-card {{
    background:{COLORS['panel']}; border:1px solid #1f2937; border-radius:14px;
    padding:22px; box-shadow:0 10px 30px rgba(0,0,0,.35);
}}
.atlas-muted {{ color:{COLORS['muted']}; font-size:13px; }}
.atlas-disclaimer {{ font-size:11px; color:{COLORS['muted']}; border-left:3px solid {COLORS['accent']}; padding:8px 12px; margin-top:14px; background:#0e1320; border-radius:0 8px 8px 0;}}

/* Inputs */
.stTextInput > div > div > input, .stTextArea textarea {{
    background:{COLORS['bg']} !important; color:{COLORS['text']} !important;
    border:1px solid #2a3344 !important; border-radius:10px;
}}
.stTextInput > div > div > input:focus {{ border-color:{COLORS['accent']} !important; }}

/* Buttons */
.stButton > button {{
    background:linear-gradient(135deg,{COLORS['accent']},#b8860b) !important;
    color:#0b0f17 !important; font-weight:700 !important; border:none !important;
    border-radius:10px !important; padding:0.5rem 1.2rem !important;
}}
.stButton > button:hover {{ filter:brightness(1.08); }}

/* Tabs */
.stTabs [data-baseweb="tab"] {{ color:{COLORS['muted']}; }}
.stTabs [aria-selected="true"] {{ color:{COLORS['accent']} !important; }}
</style>
"""
