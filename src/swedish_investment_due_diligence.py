"""Investment due diligence v2: NO ranking or buy label on missing risk data.

Analyst revisions and short interest are useful *research* components. The
old 100-point hand-assigned weekly table remains an archived discovery list,
NOT an investment recommendation. This strict gate refuses a new final
buy-confidence score until independently sourced earnings revisions, debt,
cash flow, insider/ownership, FI short interest, and current primary-market
price have been verified. No trading/order/network capabilities.
"""
from datetime import datetime, timezone
from math import isfinite
from urllib.parse import urlsplit

from src.swedish_revision_momentum import (
    earnings_consensus_revision, target_revision_momentum
)

# Intended V2 weights. A 100-point V2 score MUST NOT be displayed until
# the required source-backed financial risk/evidence modules exist.
# Earnings estimate revisions are deliberately weighted ABOVE broker
# target revisions; neither a DCF value nor a BUY label is a revision.
V2_WEIGHTS = {
    "valuation_with_sensitivity": 15,
    "operating_quality": 20,
    "earnings_estimate_revisions": 20,
    "broker_target_revision_breadth": 15,
    "fi_short_interest_and_change": 10,
    "balance_sheet_and_cashflow": 10,
    "technical_entry_quality": 5,
    "catalyst_and_event_risk": 5,
}
assert sum(V2_WEIGHTS.values()) == 100

REQUIRED_RISK_MODULES = (
    "financial_statements_and_net_debt",
    "free_cashflow_and_adjustment_quality",
    "financial_estimate_changes",
    "insider_and_major_shareholder_transactions",
    "short_interest_level_and_trend",
    "valuation_with_downside_stress_test",
    "verified_nasdaq_stockholm_quotes_and_technical_levels",
)


def _time(raw):
    if not isinstance(raw, str):
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else None


def _valid_source(uri):
    if not isinstance(uri, str):
        return False
    p = urlsplit(uri)
    return p.scheme == "https" and bool(p.netloc)


def _short_status(record, *, now, max_age_days=7):
    if not isinstance(record, dict):
        return {"verified": False, "reason": "missing_current_fi_short_interest"}
    pct, stamp = record.get("pct"), _time(record.get("date"))
    if (not isinstance(pct, (int, float)) or isinstance(pct, bool)
            or not isfinite(pct) or pct < 0 or pct > 100
            or stamp is None or not _valid_source(record.get("source"))
            or not 0 <= (now-stamp).total_seconds() <= max_age_days*86400):
        return {"verified": False, "reason": "stale_or_unverifiable_fi_short_interest"}
    return {
        "verified": True, "pct": float(pct),
        "as_of": stamp.isoformat(),
        "risk_level": ("VERY_HIGH_SHORT_INTEREST" if pct >= 10
                       else "ELEVATED_SHORT_INTEREST" if pct >= 5
                       else "LOWER_REPORTED_SHORT_INTEREST"),
        "source": record["source"],
        "source_scope": "FI_REPORTED_POSITION_TOTAL_NOT_ALL_OPEN_SHORTS",
    }


def evaluate_investment_readiness(company, *, now=None):
    """Read-only due-diligence verdict. Never treats missing as risk-free."""
    now = now or datetime.now(timezone.utc)
    if (not isinstance(company, dict)
            or not isinstance(company.get("symbol"), str)
            or not company["symbol"].strip()
            or not isinstance(company.get("broker_events"), list)):
        raise ValueError("invalid_investment_candidate")
    symbol = company["symbol"]
    broker = target_revision_momentum(
        company["broker_events"], symbol=symbol, now=now, lookback_days=90,
        minimum_brokers=3
    )
    earnings = earnings_consensus_revision(
        company.get("estimated_earnings_revision_before"),
        company.get("estimated_earnings_revision_after"), now=now
    )
    short = _short_status(company.get("fi_short"), now=now)
    completed = set()
    if (earnings["status"] == "VERIFIED_COMPARABLE_CONSENSUS_REVISIONS"):
        completed.add("financial_estimate_changes")
    if short["verified"]:
        # Current FI total alone is not sufficient: trend also required.
        before = company.get("fi_short_previous")
        if (isinstance(before, dict)
                and _short_status(before, now=now, max_age_days=35)["verified"]
                and _time(before.get("date")) < _time(company["fi_short"]["date"])):
            completed.add("short_interest_level_and_trend")
    # Other modules require *actual separate validated reports* in a future
    # ingestion stage. Do not give credit merely because a user-entered flag
    # says that the relevant data are known.
    missing = [x for x in REQUIRED_RISK_MODULES if x not in completed]
    severe = []
    if short["verified"] and short["pct"] >= 10:
        severe.append("HIGH_FI_REPORTED_SHORT_INTEREST")
    if broker["momentum_label"] == "NEGATIVE_BROKER_REVISION_BREADTH":
        severe.append("RECENT_BROKER_TARGET_CUTS_DOMINATE")
    if (earnings["status"] == "VERIFIED_COMPARABLE_CONSENSUS_REVISIONS"
            and earnings["direction"] == "DOWN"):
        severe.append("VERIFIED_EARNINGS_CONSENSUS_DOWNGRADES")
    if any(v["change_pct"] <= -10 for v in broker["fair_value_model_revisions"]):
        severe.append("MATERIAL_NEGATIVE_FAIR_VALUE_MODEL_REVISION")

    return {
        "symbol": symbol, "mic": "XSTO",
        "proposed_v2_factor_weights": V2_WEIGHTS.copy(),
        "provisional_revision_observation_only": True,
        "broker_momentum": broker,
        "earnings_momentum": earnings,
        "short_interest": short,
        "missing_risk_modules": missing,
        "risk_flags": severe,
        "legacy_100_point_score_valid_for_buy_ranking": False,
        "final_buy_opportunity_score": None,
        "reliable_probability_of_rise": None,
        "opportunity_grade": "UNVERIFIED_NOT_RANKABLE_AS_BUY",
        "investment_decision": "AVVAKTA_KOMPLETT_RISKGRANSKNING",
        "no_broker_order": True,
        "actionable": False,
    }


def evaluate_research_comparison(companies, *, now=None):
    """Compare observed broker-revision directions without inventing buys."""
    now = now or datetime.now(timezone.utc)
    rows = [evaluate_investment_readiness(x, now=now) for x in companies]
    by_direction = {
        "POSITIVE_BROKER_REVISION_BREADTH": 0,
        "MIXED_BROKER_REVISION_BREADTH": 1,
        "NEGATIVE_BROKER_REVISION_BREADTH": 2,
        "UNKNOWN_INSUFFICIENT_BROKER_COVERAGE": 3,
    }
    rows.sort(key=lambda x: (
        by_direction[x["broker_momentum"]["momentum_label"]],
        -x["broker_momentum"]["observations"], x["symbol"]
    ))
    return {
        "scope": "SELECTED_BROKER_REVISIONS_NOT_COMPLETE_STOCK_MARKET",
        "not_a_investment_buy_ranking": True,
        "no_auto_trading": True,
        "ready_to_buy_count": 0,
        "stocks": rows,
    }
