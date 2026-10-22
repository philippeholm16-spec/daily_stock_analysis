"""Transparent Swedish *fundamental* weekly buy-opportunity watch score.

This score is a ranked research shortlist, NOT a signal or prediction.
All point allocations are documented, human-reviewed judgments using
public prices, issuer reports, and cited valuation/analyst evidence.

Importantly, a newspaper BUY recommendation NEVER automatically adds points.
No score can bypass Stock Analyst's independent VERY_GOOD technical gate,
fresh authorized real-time quote, net R/R >= 2 or 1% capital risk limit.
"""
from datetime import datetime, timezone
from math import isfinite
from urllib.parse import urlsplit

WEIGHTS = {
    "valuation": 30,         # Earnings/cash flow vs price, fair value uncertainty.
    "fundamentals": 25,      # Revenue, earnings, cash generation, balance sheet.
    "catalyst": 15,          # Verifiable company event, not editorial tips.
    "entry_timing": 20,     # Observed drawdown, trend, report reaction and volatility.
    "downside_control": 10, # Risk quality: more points for *lower* downside risk.
}
MAX_SCORE = sum(WEIGHTS.values())
assert MAX_SCORE == 100


def _read_time(stamp):
    if not isinstance(stamp, str):
        raise ValueError("timestamp_missing")
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp_lacks_timezone")
    return parsed.astimezone(timezone.utc)


def _https_url(uri):
    if not isinstance(uri, str):
        return False
    parsed = urlsplit(uri)
    return parsed.scheme == "https" and bool(parsed.netloc)


def score_fundamental_watch(candidate, *, now=None):
    """Strict input validation with fully documented per-factor judgements.

    Does not calculate current market price, fair value, or technical setups.
    Those should enter as independently sourced evidence records; the
    deductions and subjective weighting remain visible to the user.
    """
    now = now or datetime.now(timezone.utc)
    if not isinstance(candidate, dict):
        raise ValueError("candidate_must_be_mapping")
    if candidate.get("mic") != "XSTO" or not candidate.get("symbol"):
        raise ValueError("unsupported_or_unidentified_stock")
    as_of = _read_time(candidate.get("reviewed_at"))
    price_as_of = _read_time(candidate.get("price_as_of"))
    price = candidate.get("reference_price_sek")
    if not isinstance(price, (int, float)) or isinstance(price, bool) or not isfinite(price) or price <= 0:
        raise ValueError("unverified_reference_price")
    review_age = (now - as_of).total_seconds()
    quote_age = (now - price_as_of).total_seconds()
    if review_age < -120 or review_age > 7*86400:
        raise ValueError("review_not_from_current_week")
    if quote_age < -120 or quote_age > 7*86400:
        raise ValueError("reference_price_too_stale")
    factors = candidate.get("factors")
    if not isinstance(factors, dict) or set(factors) != set(WEIGHTS):
        raise ValueError("all_five_scored_factors_required")
    components = {}
    for factor, ceiling in WEIGHTS.items():
        value = factors[factor]
        if not isinstance(value, dict):
            raise ValueError("invalid_factor_evidence")
        points = value.get("points")
        if (not isinstance(points, int) or isinstance(points, bool)
                or points < 0 or points > ceiling):
            raise ValueError("factor_points_out_of_bounds")
        explanation = value.get("explanation")
        urls = value.get("sources")
        if (not isinstance(explanation, str) or len(explanation.strip()) < 16
                or not isinstance(urls, list) or not urls
                or any(not _https_url(u) for u in urls)):
            raise ValueError("uncited_or_unexplained_factor")
        components[factor] = points
    total = sum(components.values())
    if total >= 75:
        category = "PRIORITERAD_FUNDAMENTAL_BEVAKNING"
    elif total >= 65:
        category = "INTRESSANT_MEN_AVVAKTA"
    else:
        category = "LAGRE_VECKOPRIORITET"
    iso = as_of.isocalendar()
    return {
        "symbol": candidate["symbol"],
        "mic": "XSTO",
        "reference_price_sek": float(price),
        "price_as_of": price_as_of.isoformat(),
        "reviewed_at": as_of.isoformat(),
        "week": f"{iso.year}-W{iso.week:02d}",
        "score": total,
        "max_score": MAX_SCORE,
        "components": components,
        "category": category,
        "score_scope": "TRANSPARENT_MANUALLY_REVIEWED_FUNDAMENTAL_RESEARCH",
        "opportunity_probabilistic_forecast": False,
        "trading_signal": None,
        "actionable": False,
        "today_buy_status": "NOT_VERIFIED_WITH_XSTO_REALTIME_AND_STOCK_ANALYST",
        "quality_warning": (
            "Subjektiv jämförande poäng, inte kalibrerad träffsäkerhet. "
            "Ingen köpsignal utan Stock Analysts separata tekniska "
            "granskning, färsk XSTO-kurs och riskkontroll."
        ),
    }


def rank_weekly_watchlist(candidates, *, now=None):
    """Deduplicate by listed share ticker; never imply the entire market was scanned."""
    now = now or datetime.now(timezone.utc)
    rows = {}
    for entry in candidates:
        score = score_fundamental_watch(entry, now=now)
        if score["symbol"] in rows:
            prior = rows[score["symbol"]]
            if score["reviewed_at"] <= prior["reviewed_at"]:
                continue
        rows[score["symbol"]] = score
    ordered = sorted(rows.values(), key=lambda x: (-x["score"], x["symbol"]))
    weeks = {x["week"] for x in ordered}
    if len(weeks) > 1:
        raise ValueError("weekly_ranking_must_use_single_iso_week")
    return {
        "week": next(iter(weeks), None),
        "candidate_count": len(ordered),
        "universe_scope": "MANUALLY_RESEARCHED_SUBSET_NOT_ALL_NASDAQ_STOCKHOLM",
        "trading_signals_enabled": False,
        "fully_independent_live_technical_scan_done": False,
        "ranked": [{**row, "rank": i+1} for i, row in enumerate(ordered)],
    }
