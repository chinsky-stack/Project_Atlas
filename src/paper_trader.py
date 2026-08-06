"""
Paper Trading Engine for Project Atlas.

SIMULATED ONLY. No broker, no real money, no network orders.
It marks a simulated book to live (or simulated) prices, realizes P&L,
and enforces the Risk Office rules IN CODE at order time:

  - conviction gate (>=7)              [Soros: high-conviction only]
  - shorts/options permission flags   [config.risk.allow_*]
  - max position size (% of equity)
  - max open positions
  - auto-cut losers at their stop     [Soros: ruthless]
  - daily loss halt                   [config.risk.max_daily_loss_pct]
  - kill-switch freeze                [config.risk.kill_switch_drawdown_pct]
    (requires an explicit, deliberate reset by the human)

State persists to data/portfolio.json so a restart doesn't wipe the book.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from risk_office import RiskOffice


@dataclass
class Position:
    ticker: str
    direction: str          # "Long" or "Short"
    qty: float
    entry: float
    stop: float
    conviction: int
    opened_at: str
    current_price: float = 0.0
    unrealized: float = 0.0
    status: str = "open"    # open | closed
    closed_at: str = ""
    exit_price: float = 0.0
    realized: float = 0.0


@dataclass
class OrderResult:
    ok: bool
    message: str
    position: Optional[Position] = None


@dataclass
class PortfolioState:
    cash: float
    peak_equity: float
    day_start_equity: float
    killswitch: bool
    created_at: str
    positions: List[Position] = field(default_factory=list)


class PaperTrader:
    def __init__(self, config: dict, market_data):
        self.config = config
        self.account = config.get("account", {})
        self.risk = config.get("risk", {})
        self.ro = RiskOffice(config)
        self.md = market_data
        self.path = Path(__file__).parent.parent / "data" / "portfolio.json"
        self._lock = threading.Lock()
        self.state = self._load()

    # ---------------------------------------------------------------
    # Persistence
    # ---------------------------------------------------------------
    def _load(self) -> PortfolioState:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        starting = float(self.account.get("starting_capital", 1000.0))
        if self.path.exists():
            try:
                with open(self.path, "r") as f:
                    raw = json.load(f)
                raw.setdefault("cash", starting)
                raw.setdefault("peak_equity", starting)
                raw.setdefault("day_start_equity", starting)
                raw.setdefault("killswitch", False)
                raw.setdefault("created_at", datetime.now().isoformat())
                raw.setdefault("positions", [])
                # Defensively rebuild Position objects (handles stale/partial data)
                rebuilt = []
                for p in raw["positions"]:
                    if not isinstance(p, dict):
                        continue
                    try:
                        rebuilt.append(Position(**{
                            "ticker": p.get("ticker", ""),
                            "direction": p.get("direction", "Long"),
                            "qty": float(p.get("qty", 0)),
                            "entry": float(p.get("entry", 0)),
                            "stop": float(p.get("stop", 0)),
                            "conviction": int(p.get("conviction", 0)),
                            "opened_at": p.get("opened_at", ""),
                            "current_price": float(p.get("current_price", 0)),
                            "unrealized": float(p.get("unrealized", 0)),
                            "status": p.get("status", "open"),
                            "closed_at": p.get("closed_at", ""),
                            "exit_price": float(p.get("exit_price", 0)),
                            "realized": float(p.get("realized", 0)),
                        }))
                    except Exception:
                        continue
                raw["positions"] = rebuilt
                return PortfolioState(**raw)
            except Exception:
                pass
        # fresh
        state = PortfolioState(
            cash=starting,
            peak_equity=starting,
            day_start_equity=starting,
            killswitch=False,
            created_at=datetime.now().isoformat(),
            positions=[],
        )
        self._save(state)
        return state

    def _save(self, state: Optional[PortfolioState] = None):
        state = state or self.state
        with open(self.path, "w") as f:
            json.dump(asdict(state), f, indent=2, default=str)

    # ---------------------------------------------------------------
    # Valuation
    # ---------------------------------------------------------------
    def _refresh_prices(self):
        for p in self.state.positions:
            if p.status == "open":
                px = self.md.get_price(p.ticker)
                p.current_price = px
                if p.direction == "Long":
                    p.unrealized = (px - p.entry) * p.qty
                else:  # Short
                    p.unrealized = (p.entry - px) * p.qty

    def _equity_locked(self) -> float:
        """Compute equity. Caller MUST hold self._lock.

        Equity = cash
                 + Σ(current_price * qty)                for longs
                 + Σ((entry - current_price) * qty)      for shorts
        This values open positions at live market, so buying a long does
        not register as a loss.
        """
        self._refresh_prices()
        equity = self.state.cash
        for p in self.state.positions:
            if p.status != "open":
                continue
            if p.direction == "Long":
                equity += p.current_price * p.qty
            else:  # Short
                equity += (p.entry - p.current_price) * p.qty
        return equity

    def equity(self) -> float:
        with self._lock:
            return self._equity_locked()

    def positions_summary(self) -> List[Dict[str, Any]]:
        with self._lock:
            self._refresh_prices()
            out = []
            for p in self.state.positions:
                if p.status != "open":
                    continue
                out.append({
                    "ticker": p.ticker,
                    "direction": p.direction,
                    "qty": p.qty,
                    "entry": p.entry,
                    "stop": p.stop,
                    "current": p.current_price,
                    "unrealized": p.unrealized,
                    "conviction": p.conviction,
                    "opened_at": p.opened_at,
                })
            return out

    def metrics(self) -> Dict[str, float]:
        eq = self._equity_locked()
        peak = self.state.peak_equity
        dd = (peak - eq) / peak if peak > 0 else 0.0
        day_loss = (self.state.day_start_equity - eq) / self.state.day_start_equity if self.state.day_start_equity > 0 else 0.0
        return {
            "equity": eq,
            "cash": self.state.cash,
            "peak_equity": peak,
            "drawdown_pct": dd * 100,
            "daily_loss_pct": day_loss * 100,
            "open_count": sum(1 for p in self.state.positions if p.status == "open"),
            "unrealized": sum(p.unrealized for p in self.state.positions if p.status == "open"),
        }

    # ---------------------------------------------------------------
    # Kill switch
    # ---------------------------------------------------------------
    def _check_killswitch(self, eq: float) -> bool:
        if self.ro.kill_switch_triggered(self.state.peak_equity, eq):
            if not self.state.killswitch:
                self.state.killswitch = True
                self._save()
            return True
        return False

    def reset_killswitch(self):
        """Deliberate human reset after a post-mortem. Re-arms peak equity."""
        with self._lock:
            eq = self._equity_locked()
            self.state.killswitch = False
            self.state.peak_equity = eq
            self.state.day_start_equity = eq
            self._save()

    # ---------------------------------------------------------------
    # Order entry (with full Risk Office enforcement)
    # ---------------------------------------------------------------
    def place_order(self, ticker: str, direction: str, conviction: int,
                    stop: float) -> OrderResult:
        ticker = ticker.upper().strip()
        direction = direction.capitalize()
        with self._lock:
            if self.state.killswitch:
                return OrderResult(False, "KILL-SWITCH ARMED. Trading frozen. Reset required after post-mortem.")

            eq = self._equity_locked()
            if self._check_killswitch(eq):
                return OrderResult(False, "Kill-switch triggered: drawdown >= limit. Trading frozen.")

            # daily loss halt
            if self.ro.daily_loss_exceeded(eq, self.state.day_start_equity):
                return OrderResult(False, f"Daily loss limit hit ({self.risk.get('max_daily_loss_pct')}%). Halt for the day.")

            # max open positions
            open_count = sum(1 for p in self.state.positions if p.status == "open")
            if open_count >= int(self.risk.get("max_open_positions", 5)):
                return OrderResult(False, f"Max open positions ({self.risk.get('max_open_positions')}) reached.")

            # get a live price for entry
            entry = self.md.get_price(ticker)
            if entry <= 0:
                return OrderResult(False, f"No valid price for {ticker}.")

            # Risk Office hard gate (uses entry/stop for sizing)
            decision = self.ro.check_idea(ticker, direction, conviction, eq, entry, stop)
            if not decision.approved:
                return OrderResult(False, f"Risk Office rejected: {decision.reason}")

            qty = decision.max_shares
            # cash check (no margin unless allowed)
            cost = qty * entry
            if not self.risk.get("allow_margin", False) and cost > self.state.cash and direction == "Long":
                # scale to available cash (safety)
                qty = int(self.state.cash / entry)
                if qty <= 0:
                    return OrderResult(False, "Insufficient cash for this position.")
                cost = qty * entry

            # open position
            pos = Position(
                ticker=ticker,
                direction=direction,
                qty=qty,
                entry=entry,
                stop=stop,
                conviction=conviction,
                opened_at=datetime.now().isoformat(),
                current_price=entry,
            )
            self.state.positions.append(pos)
            if direction == "Long":
                self.state.cash -= cost
            # Short: cash is credited the proceeds (sim); we track separately
            self._save()
            return OrderResult(True, f"{direction} {qty} {ticker} @ {entry:.2f} (stop {stop:.2f})", pos)

    # ---------------------------------------------------------------
    # Auto-cut losers + mark-to-market (call this on a timer / each tick)
    # ---------------------------------------------------------------
    def evaluate_stops(self) -> List[str]:
        """Close any open position whose price crossed its stop. Soros: ruthless."""
        events: List[str] = []
        with self._lock:
            eq = self._equity_locked()
            if self._check_killswitch(eq):
                return events
            for p in self.state.positions:
                if p.status != "open":
                    continue
                px = self.md.get_price(p.ticker)
                p.current_price = px
                hit = (p.direction == "Long" and px <= p.stop) or \
                      (p.direction == "Short" and px >= p.stop)
                if hit:
                    # close at stop (sim fill at stop)
                    fill = p.stop
                    realized = (fill - p.entry) * p.qty if p.direction == "Long" else (p.entry - fill) * p.qty
                    p.status = "closed"
                    p.closed_at = datetime.now().isoformat()
                    p.exit_price = fill
                    p.realized = realized
                    # return cash: long releases proceeds; short settles liability
                    if p.direction == "Long":
                        self.state.cash += px * p.qty
                    else:
                        self.state.cash += realized  # short profit adds, loss subtracts
                    events.append(f"STOP HIT: closed {p.direction} {p.ticker} @ {fill:.2f}, P&L {realized:+.2f}")
            # update peak
            eq = self._equity_locked()
            if eq > self.state.peak_equity:
                self.state.peak_equity = eq
            self._check_killswitch(eq)
            self._save()
        return events

    def close_position(self, ticker: str) -> OrderResult:
        with self._lock:
            for p in self.state.positions:
                if p.ticker.upper() == ticker.upper() and p.status == "open":
                    px = self.md.get_price(p.ticker)
                    realized = (px - p.entry) * p.qty if p.direction == "Long" else (p.entry - px) * p.qty
                    p.status = "closed"
                    p.closed_at = datetime.now().isoformat()
                    p.exit_price = px
                    p.realized = realized
                    p.current_price = px
                    if p.direction == "Long":
                        self.state.cash += px * p.qty
                    else:
                        self.state.cash += realized  # short profit adds, loss subtracts
                    self._save()
                    return OrderResult(True, f"Closed {p.ticker} @ {px:.2f}, P&L {realized:+.2f}", p)
            return OrderResult(False, f"No open position for {ticker}.")

    def reset_book(self):
        """Wipe simulated book back to starting capital."""
        with self._lock:
            starting = float(self.account.get("starting_capital", 1000.0))
            self.state = PortfolioState(
                cash=starting,
                peak_equity=starting,
                day_start_equity=starting,
                killswitch=False,
                created_at=datetime.now().isoformat(),
                positions=[],
            )
            self._save()
