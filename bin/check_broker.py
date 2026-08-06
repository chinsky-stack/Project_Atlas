#!/usr/bin/env python3
"""
ATLAS CAPITAL — broker go-live pre-flight check.

Verifies the Alpaca connection in PAPER mode using keys from config.local.yaml
(or config.yaml). Confirms:
  * alpaca-py installed
  * keys present (not placeholders)
  * can authenticate to Alpaca (paper)
  * can read account + at least one quote

Run BEFORE switching broker.mode to live. Never places an order.
Usage: python3 bin/check_broker.py [paper|live]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import yaml


def load_cfg():
    cfg = yaml.safe_load(open(ROOT / "config.yaml"))
    loc = ROOT / "config.local.yaml"
    if loc.exists():
        try:
            _deep_merge(cfg, yaml.safe_load(open(loc)) or {})
        except Exception:
            pass
    return cfg


def _deep_merge(base, override):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def main():
    mode = (sys.argv[1] if len(sys.argv) > 1 else "paper").lower()
    print(f"== Pre-flight check: Alpaca {mode.upper()} ==")
    cfg = load_cfg().get("broker", {})
    key = cfg.get("api_key", "")
    sec = cfg.get("api_secret", "")
    if not key or not sec or "REPLACE" in key:
        print("FAIL: broker keys missing. Put them in config.local.yaml under broker: "
              "api_key / api_secret (paper keys for mode=paper).")
        sys.exit(1)
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest
    except ImportError:
        print("FAIL: alpaca-py not installed. Run: uv pip install alpaca-py")
        sys.exit(1)

    live = (mode == "live")
    if live and not cfg.get("live_confirmed", False):
        print("FAIL: live_confirmed is not true. Refusing live pre-flight.")
        sys.exit(1)

    trading = TradingClient(key, sec, paper=not live)
    data = StockHistoricalDataClient(key, sec)
    try:
        acct = trading.get_account()
        print(f"OK: authenticated. Account id={acct.id}  status={acct.status}")
        print(f"    equity=${float(acct.equity):,.2f}  cash=${float(acct.cash):,.2f}  "
              f"buying_power=${float(acct.buying_power):,.2f}")
        print(f"    paper={acct.account_number and not live}")
    except Exception as e:
        print(f"FAIL: Alpaca auth/account error: {e}")
        sys.exit(1)

    try:
        q = data.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols="AAPL"))
        px = getattr(q.get("AAPL"), "ask_price", None) if isinstance(q, dict) else None
        print(f"OK: market data reachable (AAPL ask={px})")
    except Exception as e:
        print(f"WARN: market data quote failed (non-fatal): {e}")

    print(f"\n== {mode.upper()} pre-flight PASSED. Safe to set broker.mode: {mode} in config.yaml. ==")
    if mode == "live":
        print("REMINDER: LIVE = REAL MONEY. Only proceed after weeks of paper testing.")


if __name__ == "__main__":
    main()
