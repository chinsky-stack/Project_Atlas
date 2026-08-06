"""
Risk Office — hard gate for Project Atlas
Implements the aggressive Soros-adapted rules.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class RiskDecision:
    approved: bool
    reason: str
    max_shares: int = 0
    position_value: float = 0.0
    risk_dollars: float = 0.0


class RiskOffice:
    def __init__(self, config: dict):
        self.config = config
        self.risk = config.get("risk", {})
        self.account = config.get("account", {})

    def check_idea(self, ticker: str, direction: str, conviction: int, 
                   equity: float, entry: float, stop: float) -> RiskDecision:
        """
        Hard gate. Returns approved or rejected with reason.
        """
        # 1. Conviction filter (Soros style)
        if conviction < 7:
            return RiskDecision(
                approved=False,
                reason="Conviction below 7. Automatic NO-ACTION under Soros rules."
            )

        # 2. Direction / instrument permission
        direction_lower = direction.lower()
        if direction_lower in ["short"] and not self.risk.get("allow_shorts", False):
            return RiskDecision(False, "Shorts are currently disabled in config.")
        if direction_lower in ["call", "put"] and not self.risk.get("allow_options", False):
            return RiskDecision(False, "Options are currently disabled in config.")

        # 3. Position sizing
        risk_pct = self.risk.get("max_risk_per_trade_pct", 8.0) / 100
        risk_dollars = equity * risk_pct
        risk_per_unit = abs(entry - stop)

        if risk_per_unit <= 0:
            return RiskDecision(False, "Stop must be different from entry.")

        max_shares = int(risk_dollars / risk_per_unit)
        position_value = max_shares * entry
        max_pos_pct = self.risk.get("max_position_pct", 45.0) / 100

        if position_value > equity * max_pos_pct:
            # Scale down to max position
            max_shares = int((equity * max_pos_pct) / entry)
            position_value = max_shares * entry
            risk_dollars = max_shares * risk_per_unit

        if max_shares <= 0:
            return RiskDecision(False, "Calculated size is zero. Check prices.")

        return RiskDecision(
            approved=True,
            reason="Approved by Risk Office",
            max_shares=max_shares,
            position_value=position_value,
            risk_dollars=risk_dollars
        )

    def daily_loss_exceeded(self, current_equity: float, start_of_day_equity: float) -> bool:
        max_daily = self.risk.get("max_daily_loss_pct", 25.0) / 100
        loss_pct = (start_of_day_equity - current_equity) / start_of_day_equity
        return loss_pct >= max_daily

    def kill_switch_triggered(self, peak_equity: float, current_equity: float) -> bool:
        max_dd = self.risk.get("kill_switch_drawdown_pct", 50.0) / 100
        dd = (peak_equity - current_equity) / peak_equity
        return dd >= max_dd
