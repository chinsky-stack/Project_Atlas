"""Read-only viewer for a member's SEPARATE brokerage account.

Penn ("MASTA", $500k paper) trades this account HIMSELF. This module only
READS his account (equity, positions, orders) so Hermes/portal/digest can show
"what's up" — it exposes NO trading methods. The ATLAS auto-trader never touches
these keys (it only uses config.local.yaml `broker:` = Dr. King's account).
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus


def _member_cfg(cfg, who="penn", key_block="broker"):
    return (cfg.get("members", {}) or {}).get(who, {}).get(key_block, {}) or {}


def get_client(cfg, who="penn", key_block="broker"):
    bc = _member_cfg(cfg, who, key_block)
    key = bc.get("api_key", "")
    secret = bc.get("api_secret", "")
    if not key or not secret or "REPLACE" in key:
        return None
    return TradingClient(key, secret, paper=(bc.get("mode") != "live"))


def snapshot(cfg, who="penn", since_days=7, key_block="broker"):
    """Return dict with equity/cash/bp/positions/orders for the member account.
    Returns None if keys not configured. `key_block` selects which broker block
    under members.<who> (e.g. "broker" = MASTA, "personal_broker" = personal)."""
    t = get_client(cfg, who, key_block)
    if t is None:
        return None
    import datetime as dt
    ac = t.get_account()
    positions = t.get_all_positions()
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=since_days)
    orders = t.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.ALL, limit=200))
    wk = []
    for o in orders:
        sa = o.submitted_at
        if sa.tzinfo is None:
            sa = sa.replace(tzinfo=dt.timezone.utc)
        if sa >= since:
            wk.append(o)
    return {
        "equity": float(ac.equity),
        "cash": float(ac.cash),
        "bp": float(ac.buying_power),
        "positions": positions,
        "orders": wk,
    }
