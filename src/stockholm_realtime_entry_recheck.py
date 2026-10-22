"""Reprice Stock Analyst's indicative plan against primary XSTO live quotes.

This stage only accepts externally authorized, validated IBKR Nordic L1 ticks.
It can approve an updated PRELIMINARY PLAN for human review; not a trade order.
Historical support/resistance must also be recent. A live quote alone cannot
turn stale OHLC bars or an untested strategy into a good entry.
"""
from datetime import datetime, timezone
from math import isfinite

from src.stockholm_realtime_quality import QuoteGateResult
from src.swedish_market_scanner import Candidate, evaluate


def _positive(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(value) and value > 0


def _unavailable(reason):
    return {
        "status": "LIVE_SETUP_REJECTED",
        "reasons": [reason],
        "actionable": False,
        "trade_signal": None,
        "levels": None,
    }


def reprice_with_live_quote(analysis, quote_result, *, isin, symbol,
                            capital_sek=15000,
                            commission_sek_per_side=1.0,
                            min_slippage_sek_per_share_per_side=0.02,
                            max_reference_age_minutes=20,
                            now=None):
    """Recompute net RR and quantity using best ask as *hypothetical* entry.

    The quote_result must be produced by the strict primary live quality
    validator in-process; replay fixtures do not grant any real-world
    exchange entitlement. Upstream needs licensed recent bars and source
    provenance independently.
    """
    now = now or datetime.now(timezone.utc)
    if (not isinstance(analysis, dict)
            or analysis.get("status") != "ANALYZED_INDICATIVE_SETUP"
            or analysis.get("opportunity_grade") != "VERY_GOOD"
            or analysis.get("score", 0) < 85):
        return _unavailable("stock_analyst_not_very_good")
    if (not isinstance(quote_result, QuoteGateResult)
            or not quote_result.accepted_as_primary_live
            or not isinstance(quote_result.quote, dict)):
        return _unavailable("missing_verified_primary_realtime_quote")
    if not 10000 <= capital_sek <= 25000:
        return _unavailable("invalid_capital")
    quote = quote_result.quote
    if quote.get("isin") != isin or quote.get("symbol") != symbol:
        return _unavailable("quote_identity_does_not_match_analysis")
    if not _positive(quote.get("ask")) or not _positive(quote.get("bid")):
        return _unavailable("invalid_live_book")
    try:
        stamp = datetime.fromisoformat(analysis["chart_as_of"].replace("Z", "+00:00"))
        quote_stamp = datetime.fromisoformat(quote["as_of"].replace("Z", "+00:00"))
        if not stamp.tzinfo or not quote_stamp.tzinfo:
            raise ValueError
        bar_age = (now - stamp).total_seconds()
        quote_age = (now - quote_stamp).total_seconds()
        if (bar_age < 0 or bar_age > max_reference_age_minutes * 60
                or quote_age < -2 or quote_age > 60):
            return _unavailable("reference_bars_or_live_quote_stale")
        stop, target = (float(analysis[k])
                        for k in ("lowest_sell_point", "sell_point"))
        proposed_entry = float(analysis["entry_price"])
        new_entry = float(quote["ask"])  # conservative purchase at ask
        spread = float(quote["ask"] - quote["bid"])
        if (not all(_positive(x) for x in (stop, target, proposed_entry, new_entry))
                or not 0 < stop < new_entry < target
                or abs(new_entry / proposed_entry - 1) > 0.01):
            return _unavailable("live_entry_invalidated_historical_levels")
        outcome = evaluate(Candidate(
            isin=isin, mic="XSTO", symbol=symbol, currency="SEK",
            last_price=float(quote["last_price"]), entry=new_entry,
            stop=stop, target=target, turnover_sek=5_000_000,
            as_of=quote_stamp
        ), capital_sek=capital_sek, commission_sek_per_side=commission_sek_per_side,
            spread_sek_per_share=spread,
            slippage_sek_per_share_per_side=min_slippage_sek_per_share_per_side,
            max_age_seconds=60, now=now)
        upside = 100 * (target / new_entry - 1)
        if not outcome.eligible or upside < 3:
            return _unavailable("live_entry_rr_or_upside_below_required_threshold")
        return {
            "status": "LIVE_QUOTE_REPRICED_FOR_HUMAN_RESEARCH",
            "source": "IBKR_TWS_API",
            "rechecked_as_of": now.isoformat(),
            "reasons": ["live_xsto_primary_quote_verified",
                        "historical_levels_remain_valid",
                        "net_rr_above_2_after_live_spread_and_costs"],
            "levels": {
                "entry_ask": round(new_entry, 4),
                "stop_loss": round(stop, 4),
                "target": round(target, 4),
                "potential_pct": round(upside, 2),
                "net_rr": round(outcome.reward_to_risk, 2),
                "quantity": outcome.quantity,
                "risk_sek": round(outcome.risk_sek, 2),
            },
            "actionable": False,
            "trade_signal": None,
        }
    except (KeyError, ValueError, TypeError, OverflowError, ZeroDivisionError):
        return _unavailable("invalid_live_setup_inputs")
