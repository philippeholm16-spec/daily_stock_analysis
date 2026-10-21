"""Isolated, offline Swedish-market scanner core. No orders, APIs or notifications."""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Optional


@dataclass(frozen=True)
class Candidate:
    isin: str
    mic: str
    symbol: str
    currency: str
    last_price: float
    entry: float
    stop: float
    target: float
    turnover_sek: float
    as_of: datetime
    catalyst: bool = False


@dataclass(frozen=True)
class Decision:
    eligible: bool
    reasons: tuple[str, ...]
    quantity: int = 0
    risk_sek: float = 0.0
    reward_to_risk: float = 0.0


def evaluate(candidate: Candidate, *, capital_sek: float,
             commission_sek_per_side: float = 1.0,
             spread_sek_per_share: float = 0.02,
             slippage_sek_per_share_per_side: float = 0.02,
             max_age_seconds: int = 900,
             now: Optional[datetime] = None) -> Decision:
    """Conservative LONG-only gate. Assumes quoted prices in SEK.

    Costs include entry/exit commission, a full spread and slippage on both sides.
    No signal if any required input is missing, invalid or stale.
    """
    reasons = []
    values = (capital_sek, candidate.last_price, candidate.entry, candidate.stop,
              candidate.target, candidate.turnover_sek, commission_sek_per_side,
              spread_sek_per_share, slippage_sek_per_share_per_side)
    if any(not isinstance(v, (int, float)) or not isfinite(v) for v in values):
        return Decision(False, ("missing_or_nonfinite_numeric_data",))
    if capital_sek <= 0 or candidate.turnover_sek < 0 or any(v < 0 for v in
            (commission_sek_per_side, spread_sek_per_share, slippage_sek_per_share_per_side)):
        reasons.append("invalid_amount")
    if candidate.currency != "SEK" or candidate.mic != "XSTO":
        reasons.append("unsupported_currency_or_market")
    if not (len(candidate.isin) == 12 and candidate.isin[:2] == "SE"
            and candidate.isin[2:].isalnum() and candidate.symbol.strip()):
        reasons.append("invalid_instrument_identity")
    if not (0 < candidate.stop < candidate.entry < candidate.target and candidate.last_price > 0):
        reasons.append("invalid_price_levels")
    current = now or datetime.now(timezone.utc)
    if (candidate.as_of is None or candidate.as_of.tzinfo is None
            or current.tzinfo is None):
        reasons.append("missing_or_naive_timestamp")
    elif (current - candidate.as_of).total_seconds() > max_age_seconds or candidate.as_of > current:
        reasons.append("stale_or_future_quote")
    if reasons:
        return Decision(False, tuple(reasons))
    unit_cost = spread_sek_per_share + 2 * slippage_sek_per_share_per_side
    unit_risk = candidate.entry - candidate.stop + unit_cost
    unit_reward = candidate.target - candidate.entry - unit_cost
    fixed_cost = 2 * commission_sek_per_side
    risk_budget = capital_sek * 0.01
    # Position sizing must meet BOTH the 1%-of-equity risk budget and the
    # unleveraged cash budget. Entry capital includes entry commission plus
    # conservative half-spread and one-sided slippage.
    risk_quantity = max(0, int((risk_budget - fixed_cost) // unit_risk))
    estimated_entry_cost = (candidate.entry + spread_sek_per_share / 2
                            + slippage_sek_per_share_per_side)
    cash_quantity = max(0, int((capital_sek - commission_sek_per_side)
                               // estimated_entry_cost))
    quantity = min(risk_quantity, cash_quantity)
    if risk_quantity == 0:
        reasons.append("insufficient_risk_budget")
    if cash_quantity == 0:
        reasons.append("insufficient_cash")
    if reasons:
        return Decision(False, tuple(reasons))
    risk = quantity * unit_risk + fixed_cost
    reward = quantity * unit_reward - fixed_cost
    rr = reward / risk
    if risk > risk_budget + 1e-9:
        reasons.append("risk_above_one_percent")
    if rr < 2:
        reasons.append("reward_to_risk_below_two")
    if quantity * estimated_entry_cost + commission_sek_per_side > capital_sek + 1e-9:
        reasons.append("insufficient_cash")
    return Decision(not reasons, tuple(reasons), quantity, risk, rr)
