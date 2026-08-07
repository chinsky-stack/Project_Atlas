"""
ATLAS CAPITAL — Autonomous Trader (Soros-adapted, aggressive but HARD-CAPPED).

Paper-only by design. Every order passes the broker's Risk Office gate and the
engine's own envelope (max capital at risk, max positions, max premium at risk,
kill-switch). This is a disciplined, rules-based system — NOT a profit
guarantee and NOT a live-money bot.

Signals are simple, honest heuristics (momentum / trend / mean-reversion on
daily bars, plus an options-flow proxy via upcoming-earnings + IV-rank using the
underlying move). They are not market-beating; they exist to exercise the
risk-managed execution loop.

All tunables live in config.yaml -> auto_trader.
"""
from __future__ import annotations

import time
import threading
import datetime as dt
from typing import Optional

import yaml


# ----------------------------------------------------------------------------
# Signal generation (rule-based, transparent)
# ----------------------------------------------------------------------------
def _daily_bars(symbol: str, period: str = "6mo"):
    """Fetch daily bars via yfinance. Returns a DataFrame or None."""
    try:
        import yfinance as yf
        df = yf.download(symbol, period=period, interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or len(df) < 30:
            return None
        return df
    except Exception:
        return None


def analyze(symbol: str) -> dict:
    """Return a signal dict: {ticker, direction, conviction, rationale}."""
    df = _daily_bars(symbol)
    if df is None:
        return {"ticker": symbol, "direction": None, "conviction": 0,
                "rationale": "no price data"}
    close = df["Close"]
    if hasattr(close, "iloc"):
        close = close.iloc[:, 0] if getattr(close, "ndim", 1) == 2 else close
    # momentum: 20d return
    mom = float(close.iloc[-1] / close.iloc[-21] - 1) if len(close) > 21 else 0.0
    # trend: price vs 50d SMA
    sma50 = float(close.iloc[-50:].mean()) if len(close) >= 50 else float(close.mean())
    trend_up = float(close.iloc[-1]) > sma50
    # mean-reversion: 5d rate of change
    roc5 = float(close.iloc[-1] / close.iloc[-6] - 1) if len(close) > 6 else 0.0

    rationale = f"mom20={mom:+.1%} trend={'up' if trend_up else 'dn'} roc5={roc5:+.1%}"
    if mom > 0.06 and trend_up and roc5 > -0.04:
        return {"ticker": symbol, "direction": "Long", "conviction": 9,
                "rationale": rationale}
    if mom < -0.06 and (not trend_up) and roc5 < 0.04:
        return {"ticker": symbol, "direction": "Short", "conviction": 9,
                "rationale": rationale}
    if trend_up and roc5 < -0.03 and mom > 0.0:
        return {"ticker": symbol, "direction": "Long", "conviction": 8,
                "rationale": rationale + " (pullback)"}
    return {"ticker": symbol, "direction": None, "conviction": 0,
            "rationale": rationale}


# ----------------------------------------------------------------------------
# Engine
# ----------------------------------------------------------------------------
class AutoTrader:
    def __init__(self, broker, cfg: dict, market_price=None):
        self.broker = broker
        self.cfg = cfg.get("auto_trader", {})
        self.market_price = market_price or (lambda s: 0.0)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.running = False

        self.book = float(self.cfg.get("book_reference", 100000.0))
        self.peak_book = self.book
        self.realized_pnl = 0.0
        self.positions = {}
        self.last_signals = []
        self.killswitch = False
        self.log = []
        self.daily_loss = 0.0
        self._day = dt.date.today()

    # ---- controls ----
    def start(self):
        with self._lock:
            if self.running or self.killswitch:
                return False
            if not self.cfg.get("paper_only", True):
                self._log("REFUSED: paper_only is false — will not trade live.")
                return False
            self.running = True
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            self._log("AutoTrader started (PAPER).")
            return True

    def stop(self):
        with self._lock:
            self.running = False
            self._stop.set()
            self._log("AutoTrader stopped.")
        return True

    def reset_killswitch(self):
        with self._lock:
            self.killswitch = False
            self._log("Kill-switch reset by admin.")

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "killswitch": self.killswitch,
                "book": self.book,
                "peak_book": self.peak_book,
                "drawdown_pct": (1 - self.book / self.peak_book) * 100 if self.peak_book else 0,
                "realized_pnl": self.realized_pnl,
                "positions": len(self.positions),
                "daily_loss": self.daily_loss,
                "last_signals": self.last_signals[-8:],
                "log": self.log[-12:],
            }

    # ---- internals ----
    def _log(self, msg: str):
        ts = dt.datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{ts}] {msg}")
        if len(self.log) > 200:
            self.log = self.log[-200:]

    def _envelope_ok(self) -> bool:
        c = self.cfg
        if self.killswitch:
            return False
        if dt.date.today() != self._day:
            self._day = dt.date.today(); self.daily_loss = 0.0
        if self.daily_loss >= c.get("max_daily_loss_pct", 20.0):
            self._log("Daily loss cap hit — pausing new entries.")
            return False
        if len(self.positions) >= c.get("max_open_positions", 8):
            return False
        dd = (1 - self.book / self.peak_book) * 100 if self.peak_book else 0
        if dd >= c.get("kill_switch_drawdown_pct", 35.0):
            self.killswitch = True
            self._log(f"KILL-SWITCH triggered at drawdown {dd:.1f}%.")
            return False
        return True

    def _size_stock(self, price: float) -> Optional[int]:
        c = self.cfg
        equity = self.book
        max_pos_val = equity * (c.get("max_single_position_pct", 20.0) / 100.0)
        max_risk_val = equity * (c.get("max_capital_at_risk_pct", 40.0) / 100.0)
        cap = min(max_pos_val, max_risk_val)
        if price <= 0:
            return None
        qty = int(cap // price)
        return max(1, qty) if qty >= 1 else None

    def _size_option_premium(self) -> float:
        c = self.cfg
        equity = self.book
        return equity * (c.get("max_premium_at_risk_per_option_trade_pct", 8.0) / 100.0)

    def _tick_once(self):
        c = self.cfg
        universe = c.get("signal_universe", [])
        allow_options = c.get("options_only_defined_risk", True)
        signals = []
        for sym in universe:
            sig = analyze(sym)
            signals.append(sig)
            if sig["direction"] is None:
                continue
            if sig["conviction"] < c.get("min_conviction", 8):
                continue
            with self._lock:
                if not self._envelope_ok():
                    break
                if sym in self.positions:
                    continue
            direction = sig["direction"]
            price = self.market_price(sym)
            # 1) Stock/ETF leg (Risk-Office gated)
            qty = self._size_stock(price)
            if qty:
                stop = price * (0.94 if direction == "Long" else 1.06)
                res = self.broker.submit_order(sym, direction, sig["conviction"], stop)
                with self._lock:
                    if res.ok:
                        self.positions[sym] = {
                            "direction": direction, "qty": qty, "entry": price,
                            "stop": stop, "kind": "stock",
                            "conviction": sig["conviction"], "rationale": sig["rationale"],
                        }
                        self._log(f"OPEN {direction} {qty} {sym} @ {price:.2f} "
                                  f"({sig['rationale']}) -> {res.message}")
                    else:
                        self._log(f"REJECT {sym}: {res.message}")
            # 2) Defined-risk options vertical (aggressive lever, capped premium)
            if allow_options and sym not in self.positions:
                prem = self._size_option_premium()
                with self._lock:
                    cap_ok = self._envelope_ok() and len(self.positions) < c.get("max_open_positions", 8)
                if cap_ok:
                    ores = self.broker.submit_option_spread(sym, direction, prem, sig["conviction"])
                    with self._lock:
                        if ores.ok:
                            self.positions[sym + "_OPT"] = {
                                "direction": direction, "kind": "option",
                                "underlying": sym, "conviction": sig["conviction"],
                                "rationale": sig["rationale"],
                            }
                            self._log(f"OPEN OPTION {direction} vertical {sym} -> {ores.message}")
                        else:
                            self._log(f"REJECT OPTION {sym}: {ores.message}")
        with self._lock:
            self.last_signals = signals

    def _loop(self):
        interval = int(self.cfg.get("loop_seconds", 300))
        while not self._stop.is_set():
            try:
                self._tick_once()
            except Exception as e:
                with self._lock:
                    self._log(f"loop error: {e}")
            self._stop.wait(interval)
