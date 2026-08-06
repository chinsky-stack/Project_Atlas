"""
Strategy Lab — high-conviction idea intake (persisted to disk)
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class Idea:
    ticker: str
    direction: str
    thesis: str
    edge_source: str
    who_loses: str
    conviction: int
    horizon: str
    status: str = "pending"
    submitted_at: str = ""


IDEAS_PATH = Path(__file__).parent.parent / "data" / "ideas.json"


class StrategyLab:
    def __init__(self):
        self.path = IDEAS_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> List[dict]:
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def _write(self, data):
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def submit(self, ticker: str, direction: str, thesis: str,
               edge_source: str, who_loses: str, conviction: int, horizon: str) -> Idea:

        # Hard filters from Claude review + Soros style
        if not edge_source or edge_source.lower() in ["none", "unknown", ""]:
            raise ValueError("Edge source is required. Idea rejected.")

        if conviction < 7:
            raise ValueError("Conviction < 7 → automatic NO-ACTION under Soros rules.")

        idea = Idea(
            ticker=ticker.upper(),
            direction=direction,
            thesis=thesis,
            edge_source=edge_source,
            who_loses=who_loses,
            conviction=conviction,
            horizon=horizon,
            status="accepted_for_risk_check",
            submitted_at=datetime.now().isoformat(),
        )
        data = self._read()
        data.append(asdict(idea))
        self._write(data)
        return idea

    def get_all(self) -> List[dict]:
        return self._read()
