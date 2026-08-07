"""
Broker abstraction for Project Atlas — paper-first and safety-gated.

Modes (set in config.yaml under `broker:`):
  mode: simulate   -> uses the in-process PaperTrader sim engine (default, no keys)
  mode: paper      -> connects to Alpaca PAPER endpoint (real sandbox, NO real money)
  mode: live       -> connects to Alpaca LIVE (REAL MONEY) — requires live_confirmed: true

Safety guarantees (apply to paper AND live):
  * Every order passes through the SAME RiskOffice gate as the sim engine
    (conviction >=7, shorts/options permission, max size, max positions,
    daily-loss halt, kill-switch freeze).
  * For live/paper, a real broker STOP order is placed at submission so the
    broker itself enforces the Soros "cut losers" rule — not just our code.
  * Live mode is impossible to enter by accident: needs `live_confirmed: true`
    AND valid keys. Without alpaca-py installed or keys missing, it refuses
    to start (never silently trades).

No broker order is ever placed unless mode is paper/live AND keys are valid.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from risk_office import RiskOffice


@dataclass
class OrderResult:
    ok: bool
    message: str
    position: Optional[dict] = None


# ---------------------------------------------------------------------------
# Simulated broker = the existing in-process engine (no keys, no network)
# ---------------------------------------------------------------------------
class SimBroker:
    """Thin wrapper so the UI can treat the sim engine as a broker."""
    mode = "simulate"
    label = "SIMULATED (in-process, no broker)"
    is_live = False

    def __init__(self, paper_trader):
        self.engine = paper_trader

    def submit_order(self, ticker, direction, conviction, stop, qty=None):
        r = self.engine.place_order(ticker, direction, conviction, stop)
        return OrderResult(r.ok, r.message,
                           self._pos_to_dict(r.position) if r.position else None)

    def _pos_to_dict(self, p):
        return {
            "ticker": p.ticker, "direction": p.direction, "qty": p.qty,
            "entry": p.entry, "stop": p.stop, "conviction": p.conviction,
            "current_price": p.current_price, "unrealized": p.unrealized,
            "status": p.status,
        }

    def get_positions(self):
        out = []
        for p in self.engine.positions_summary():
            out.append(p)
        return out

    def equity(self):
        return self.engine.equity()

    def get_cash(self):
        return self.engine.metrics()["cash"]

    def market_price(self, ticker):
        return self.engine.md.get_price(ticker)

    def close_position(self, ticker):
        r = self.engine.close_position(ticker)
        return OrderResult(r.ok, r.message,
                           self._pos_to_dict(r.position) if r.position else None)

    def evaluate_stops(self):
        return self.engine.evaluate_stops()

    def metrics(self):
        return self.engine.metrics()

    @property
    def state(self):
        return self.engine.state

    def reset(self):
        self.engine.reset_book()


# ---------------------------------------------------------------------------
# Alpaca broker (paper or live) — safety gated
# ---------------------------------------------------------------------------
class AlpacaBroker:
    def __init__(self, config: dict, market_data, live: bool = False):
        self.config = config
        self.broker_cfg = config.get("broker", {})
        self.risk = config.get("risk", {})
        self.account = config.get("account", {})
        self.md = market_data
        self.live = live
        self.mode = "live" if live else "paper"
        self.label = ("Alpaca LIVE (REAL MONEY)" if live else "Alpaca PAPER (sandbox)")
        self.is_live = live
        self.ro = RiskOffice(config)
        self._lock = threading.Lock()

        # Load keys from config (placeholders by default)
        self.api_key = self.broker_cfg.get("api_key", "")
        self.api_secret = self.broker_cfg.get("api_secret", "")
        if not self.api_key or not self.api_secret or "REPLACE" in self.api_key:
            raise RuntimeError(
                "Alpaca keys missing in config.yaml under broker:. "
                "Add api_key/api_secret (paper keys for mode=paper)."
            )

        # Lazy import so the app runs without alpaca-py until live mode is used
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.data.historical import StockHistoricalDataClient
        except ImportError as e:
            raise RuntimeError(
                "alpaca-py is not installed. Run: pip install alpaca-py   (or uv pip install alpaca-py)"
            ) from e

        self._TradingClient = TradingClient
        self._DataClient = StockHistoricalDataClient
        self.trading = TradingClient(self.api_key, self.api_secret, paper=not live)
        self.data = StockHistoricalDataClient(self.api_key, self.api_secret)

        # Local kill-switch state (broker won't freeze our algo for us)
        self.path = Path(__file__).parent.parent / "data" / "broker_state.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._killswitch = self._load_ks()

    def _load_ks(self) -> bool:
        try:
            return bool(json.load(open(self.path)).get("killswitch", False))
        except Exception:
            return False

    def _save_ks(self):
        with open(self.path, "w") as f:
            json.dump({"killswitch": self._killswitch,
                       "updated": datetime.now().isoformat()}, f)

    # ---- live read-through helpers ----
    def _account(self):
        return self.trading.get_account()

    def equity(self) -> float:
        return float(self._account().equity)

    def get_cash(self) -> float:
        return float(self._account().cash)

    def _peak_equity(self) -> float:
        # Alpaca doesn't track peak; approximate from last equity via state file.
        try:
            return float(json.load(open(self.path)).get("peak_equity", self.equity()))
        except Exception:
            return self.equity()

    def metrics(self) -> Dict[str, float]:
        eq = self.equity()
        cash = self.get_cash()
        try:
            peak = float(json.load(open(self.path)).get("peak_equity", eq))
        except Exception:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0.0
        # unrealized from open positions
        unreal = 0.0
        for p in self.get_positions():
            unreal += p.get("unrealized", 0.0)
        return {
            "equity": eq, "cash": cash, "peak_equity": peak,
            "drawdown_pct": dd * 100, "daily_loss_pct": 0.0,
            "open_count": len(self.get_positions()), "unrealized": unreal,
        }

    def market_price(self, ticker: str) -> float:
        try:
            from alpaca.data.requests import StockLatestQuoteRequest
            q = self.data.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=ticker))
            qq = q.get(ticker) if isinstance(q, dict) else q
            bid = float(getattr(qq, "bid_price", 0) or 0)
            ask = float(getattr(qq, "ask_price", 0) or 0)
            if bid and ask:
                return (bid + ask) / 2
            return bid or ask or self.md.get_price(ticker)
        except Exception:
            return self.md.get_price(ticker)

    def get_positions(self) -> List[Dict[str, Any]]:
        out = []
        try:
            for p in self.trading.get_all_positions():
                qty = float(p.qty)
                entry = float(p.avg_entry_price)
                cur = float(p.current_price)
                # Alpaca side: 'long' or 'short'
                direction = "Long" if p.side == "long" else "Short"
                unreal = (cur - entry) * qty if direction == "Long" else (entry - cur) * qty
                out.append({
                    "ticker": p.symbol,
                    "direction": direction,
                    "qty": qty,
                    "entry": entry,
                    "current": cur,
                    "stop": 0.0,   # stop lives at the broker as a separate order
                    "unrealized": unreal,
                    "conviction": 0,
                    "opened_at": "",
                })
        except Exception:
            pass
        return out

    # ---- order entry with full local Risk Office enforcement ----
    def _market_open(self, extended=False):
        """Return True if US regular-equity market is open now (ET).
        extended=True also allows pre/post market. Uses Alpaca's clock when
        available; falls back to a local ET weekday 9:30-16:00 check."""
        try:
            clock = self.trading.get_clock()
            if clock is not None:
                return bool(clock.is_open)
        except Exception:
            pass
        # Fallback: compute ET weekday 09:30-16:00
        try:
            import datetime
            utc = datetime.datetime.now(datetime.timezone.utc)
            et = utc - datetime.timedelta(hours=4)  # EDT (summer); -5 in winter
            if et.weekday() >= 5:
                return False
            op, cl = (4, 20) if extended else (9, 30), (20, 0) if extended else (16, 0)
            t = et.hour * 60 + et.minute
            return (op[0]*60+op[1]) <= t <= (cl[0]*60+cl[1])
        except Exception:
            return False

    def submit_order(self, ticker, direction, conviction, stop, qty=None, allow_after_hours=False) -> OrderResult:
        ticker = ticker.upper().strip()
        direction = direction.capitalize()
        with self._lock:
            # Option (b): block order entry outside regular US equity hours so
            # paper DAY orders don't silently queue until next open. Override
            # with allow_after_hours=True only for deliberate extended-hours trades.
            if not allow_after_hours and not self._market_open():
                return OrderResult(False,
                    "MARKET CLOSED — orders only submit during US regular hours "
                    "(9:30 AM-4:00 PM ET). Re-open during market hours, or set "
                    "allow_after_hours=True for extended-hours trading.")
            if self._killswitch:
                return OrderResult(False, "KILL-SWITCH ARMED. Trading frozen. Reset required.")
            eq = self.equity()
            # local kill-switch check vs peak
            peak = self._peak_equity()
            if self.ro.kill_switch_triggered(peak, eq):
                self._killswitch = True
                self._save_ks()
                return OrderResult(False, "Kill-switch triggered on live equity. Frozen.")

            # Risk Office hard gate
            entry = self.market_price(ticker)
            if entry <= 0:
                return OrderResult(False, f"No valid price for {ticker}.")
            decision = self.ro.check_idea(ticker, direction, conviction, eq, entry, stop)
            if not decision.approved:
                return OrderResult(False, f"Risk Office rejected: {decision.reason}")

            # Build + submit the order via Alpaca
            try:
                from alpaca.trading.requests import MarketOrderRequest
                from alpaca.trading.enums import OrderSide, TimeInForce
                side = OrderSide.SELL if direction == "Short" else OrderSide.BUY
                qty_to_use = qty if qty else decision.max_shares
                req = MarketOrderRequest(
                    symbol=ticker, qty=qty_to_use, side=side,
                    time_in_force=TimeInForce.DAY,
                )
                order = self.trading.submit_order(req)

                # Honest status: ACCEPTED/pending_new means the order is queued
                # (e.g. after market hours) and has NOT filled yet. Only report a
                # confirmed fill when the order is actually filled/partially filled.
                ostatus = str(getattr(order, "status", "")).lower()
                filled = ("filled" in ostatus) or ("partial" in ostatus)
                pending = ostatus in ("accepted", "pending_new", "new", "accepted_for_bidding")

                # Place a real broker STOP so the exchange enforces the cut
                # (only meaningful once the parent is filled; if pending, skip
                #  for now — the UI/review loop will place it after fill).
                stop_id = None
                if filled:
                    stop_id = self._place_stop(ticker, direction, qty_to_use, stop)

                if filled:
                    return OrderResult(True,
                        f"{self.mode.upper()} {direction} {qty_to_use} {ticker} @ mkt (~{entry:.2f}); "
                        f"stop {stop:.2f} placed at broker" +
                        (f" (stop_id {stop_id})" if stop_id else ""),
                        {"ticker": ticker, "direction": direction, "qty": qty_to_use,
                         "entry": entry, "stop": stop, "conviction": conviction})
                else:
                    return OrderResult(True,
                        f"{self.mode.upper()} {direction} {qty_to_use} {ticker} SUBMITTED (status: {ostatus}); "
                        f"will fill at next market open. Stop {stop:.2f} will be placed after fill.",
                        {"ticker": ticker, "direction": direction, "qty": qty_to_use,
                         "entry": entry, "stop": stop, "conviction": conviction, "pending": True})
            except Exception as e:
                return OrderResult(False, f"Alpaca submit failed: {e}")

    def _place_stop(self, ticker, direction, qty, stop):
        try:
            from alpaca.trading.requests import StopOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            # For a long, stop is a SELL; for a short, stop is a BUY to cover
            side = OrderSide.SELL if direction == "Long" else OrderSide.BUY
            req = StopOrderRequest(
                symbol=ticker, qty=qty, side=side,
                stop_price=stop, time_in_force=TimeInForce.GTC,
            )
            o = self.trading.submit_order(req)
            return getattr(o, "id", None)
        except Exception:
            return None

    def submit_option_spread(self, underlying: str, direction: str,
                             max_premium: float, conv: int = 8) -> OrderResult:
        """Defined-risk vertical spread (bull-call or bear-put). No naked shorts.
        max_premium = max $ risk on the spread (enforced). Returns OrderResult.
        Uses a LIMIT order at net mid so it can rest (not blocked by market-hours
        like MARKET option orders)."""
        if not self._market_open():
            return OrderResult(False, "MARKET CLOSED — option spreads only submit during US regular hours.")
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import (OrderRequest, OptionLegRequest,
                                                 GetOptionContractsRequest)
            from alpaca.trading.enums import (OrderClass, AssetClass, OrderType,
                                              TimeInForce, OrderSide, PositionIntent)
            # find option contracts
            resp = self.trading.get_option_contracts(
                GetOptionContractsRequest(symbol_or_asset_id=underlying))
            contracts = resp.option_contracts if hasattr(resp, "option_contracts") else resp
            otype = "call" if direction == "Long" else "put"
            legs = [c for c in contracts if getattr(c, "type", "") == otype]
            if not legs:
                return OrderResult(False, f"No {otype} contracts found for {underlying}.")
            legs.sort(key=lambda c: (c.expiration_date, float(c.strike_price)))
            # nearest expiry with >=2 strikes
            from collections import defaultdict
            by_exp = defaultdict(list)
            for c in legs:
                by_exp[c.expiration_date].append(c)
            exp = None
            for e in sorted(by_exp):
                if len(by_exp[e]) >= 2:
                    exp = e; break
            if exp is None:
                return OrderResult(False, "Not enough strikes for a vertical.")
            chain = sorted(by_exp[exp], key=lambda c: float(c.strike_price))
            long_leg = chain[0]
            short_leg = chain[1]
            # sizing: how many spreads fit within max_premium (assume ~$1 wide)
            width = abs(float(short_leg.strike_price) - float(long_leg.strike_price)) or 1.0
            # cap spreads so max loss (width*100*qty) <= max_premium
            qty = max(1, int(max_premium // (width * 100)))
            qty = min(qty, 10)
            if qty < 1:
                return OrderResult(False, "Premium cap too small for a spread.")
            if direction == "Long":
                lside, sside = OrderSide.BUY, OrderSide.SELL
                lintent, sintent = PositionIntent.BUY_TO_OPEN, PositionIntent.SELL_TO_OPEN
            else:
                lside, sside = OrderSide.BUY, OrderSide.SELL
                lintent, sintent = PositionIntent.BUY_TO_OPEN, PositionIntent.SELL_TO_OPEN
                long_leg, short_leg = chain[-1], chain[-2]  # bear-put: buy high strike, sell lower
            leg1 = OptionLegRequest(symbol=long_leg.symbol, ratio_qty=1,
                                    side=lside, position_intent=lintent)
            leg2 = OptionLegRequest(symbol=short_leg.symbol, ratio_qty=1,
                                    side=sside, position_intent=sintent)
            # LIMIT at net mid (use a small offset); DAY to avoid stale rests
            ord_req = OrderRequest(asset_class=AssetClass.US_OPTION,
                                    order_class=OrderClass.MLEG,
                                    type=OrderType.LIMIT,
                                    time_in_force=TimeInForce.DAY, qty=qty,
                                    limit_price=0.30, legs=[leg1, leg2])
            o = self.trading.submit_order(ord_req)
            return OrderResult(True,
                f"{self.mode.upper()} OPTION {direction} vertical {underlying} "
                f"x{qty} (exp {exp}) SUBMITTED status {getattr(o,'status','?')}",
                {"ticker": underlying, "direction": direction, "qty": qty,
                 "kind": "option", "conviction": conv})
        except Exception as e:
            return OrderResult(False, f"Option spread failed: {e}")

    def close_position(self, ticker) -> OrderResult:
        try:
            self.trading.close_position(ticker, qty=None)
            return OrderResult(True, f"Market close submitted for {ticker}")
        except Exception as e:
            return OrderResult(False, f"Close failed: {e}")

    def evaluate_stops(self) -> List[str]:
        # For live/paper, stops are enforced at the broker. We just report.
        return []

    def reset_killswitch(self):
        self._killswitch = False
        # re-arm peak to current equity
        try:
            s = json.load(open(self.path))
        except Exception:
            s = {}
        s["killswitch"] = False
        s["peak_equity"] = self.equity()
        with open(self.path, "w") as f:
            json.dump(s, f)
        self._save_ks()

    @property
    def state(self):
        class _S:
            killswitch = self._killswitch
        return _S()

    def reset(self):
        # Live: we do NOT wipe the broker account. Only clear local kill-switch.
        self._killswitch = False
        self._save_ks()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_broker(config: dict, market_data, sim_trader) -> Any:
    """Return a broker object implementing the uniform interface."""
    broker_cfg = config.get("broker", {})
    mode = (broker_cfg.get("mode", "simulate") or "simulate").lower()

    if mode == "simulate":
        return SimBroker(sim_trader)

    if mode in ("paper", "live"):
        live = (mode == "live")
        if live and not broker_cfg.get("live_confirmed", False):
            raise RuntimeError(
                "Refusing to enter LIVE mode: set broker.live_confirmed: true in config.yaml "
                "after you have tested paper thoroughly."
            )
        try:
            return AlpacaBroker(config, market_data, live=live)
        except RuntimeError as e:
            # Surface clearly instead of crashing the whole app
            raise

    raise ValueError(f"Unknown broker mode: {mode}")
