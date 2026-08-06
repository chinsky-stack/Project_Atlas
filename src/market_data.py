"""
Market data feed for Project Atlas.

Primary source: yfinance (live, delayed quotes).
Fallback: a deterministic simulated feed so testing never blocks on
network/API availability. Selects automatically.

IMPORTANT: This is a read-only price feed. It places NO orders and moves
NO real money. It exists only to make the paper engine behave like live.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class Quote:
    ticker: str
    price: float
    ts: datetime
    source: str  # "yfinance" or "sim"
    prev_close: float = 0.0


class MarketData:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._lock = threading.Lock()
        self._prices: Dict[str, Quote] = {}
        self._seeds: Dict[str, float] = {}
        self._use_yfinance = True
        self._yf = None
        self._probe_yfinance()

    # ---------------------------------------------------------------
    # Source selection
    # ---------------------------------------------------------------
    def _probe_yfinance(self):
        """Try to import yfinance once; degrade to sim if unavailable."""
        try:
            import yfinance as yf  # noqa: F401
            self._yf = yf
            self._use_yfinance = True
        except Exception:
            self._use_yfinance = False

    @property
    def source_name(self) -> str:
        return "yfinance (live)" if self._use_yfinance else "simulated"

    # ---------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------
    def quote(self, ticker: str) -> Quote:
        ticker = ticker.upper().strip()
        if self._use_yfinance:
            q = self._quote_yfinance(ticker)
            if q is not None:
                with self._lock:
                    self._prices[ticker] = q
                return q
        # Fallback path
        return self._quote_sim(ticker)

    def get_price(self, ticker: str) -> float:
        return self.quote(ticker).price

    # ---------------------------------------------------------------
    # yfinance path
    # ---------------------------------------------------------------
    def _quote_yfinance(self, ticker: str) -> Optional[Quote]:
        try:
            tk = self._yf.Ticker(ticker)
            # fast= True avoids the slower full history pull
            info = tk.fast_info
            price = float(getattr(info, "last_price", None) or info.get("last_price"))
            prev_close = float(getattr(info, "previous_close", 0.0) or 0.0)
            if price and price > 0:
                return Quote(
                    ticker=ticker,
                    price=price,
                    ts=datetime.now(),
                    source="yfinance",
                    prev_close=prev_close,
                )
        except Exception:
            # any failure -> sim fallback
            pass
        return None

    # ---------------------------------------------------------------
    # Simulated path (deterministic random walk around a seed price)
    # ---------------------------------------------------------------
    def _seed(self, ticker: str) -> float:
        with self._lock:
            if ticker not in self._seeds:
                # stable per-ticker starting price so it doesn't jump each call
                random.seed(hash(ticker) & 0xFFFFFFFF)
                self._seeds[ticker] = round(random.uniform(20, 400), 2)
            return self._seeds[ticker]

    def _quote_sim(self, ticker: str) -> Quote:
        with self._lock:
            last = self._prices.get(ticker)
            if last is not None:
                base = last.price
            else:
                base = self._seed(ticker)
            # small random walk step
            drift = random.uniform(-0.012, 0.012)
            new_price = max(0.5, round(base * (1 + drift), 2))
            q = Quote(
                ticker=ticker,
                price=new_price,
                ts=datetime.now(),
                source="sim",
                prev_close=self._seed(ticker),
            )
            self._prices[ticker] = q
            return q
