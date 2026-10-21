"""Review EVERY discovery row before inclusion in a Telegram research digest.

Only informational research candidates may pass. This does not constitute a
second AI opinion or approval of trades: it is a deterministic fail-closed gate.
"""
from datetime import datetime, timezone
from math import isfinite
from urllib.parse import urlsplit


TRUSTED_ARTICLE_DOMAINS = frozenset({
    "placera.se", "www.placera.se", "view.news.eu.nasdaq.com",
    "news.google.com",
})


def _fresh_timestamp(value, now, max_age_seconds):
    if not isinstance(value, str):
        return False
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (when.tzinfo is not None and
                0 <= (now - when).total_seconds() <= max_age_seconds)
    except ValueError:
        return False


def _positive(value):
    return (isinstance(value, (float, int)) and not isinstance(value, bool)
            and isfinite(value) and value > 0)


def _check_independent_analyst(row, *, capital_sek):
    """Audit Stock Analyst results independently of publisher/discovery scores."""
    output = row.get("stock_analyst")
    if not isinstance(output, dict):
        return ["stock_analyst_analysis_missing"]
    reasons = []
    if (output.get("engine") != "Stock Analyst Sweden / independent technical v1"
            or output.get("source_news_opinion_used") is not False
            or output.get("actionable") is not False
            or output.get("data_verified_real_time") is not False):
        reasons.append("unverified_or_publisher_influenced_analysis")
    status = output.get("status")
    if status not in ("ANALYSIS_UNAVAILABLE", "ANALYZED_NO_VALID_SETUP",
                      "ANALYZED_INDICATIVE_SETUP"):
        reasons.append("invalid_analyst_status")
    score = output.get("score")
    if status == "ANALYSIS_UNAVAILABLE":
        if score is not None:
            reasons.append("unavailable_analysis_has_score")
    elif (not isinstance(score, (float, int)) or isinstance(score, bool)
          or not isfinite(score) or not 0 <= score <= 100):
        reasons.append("invalid_analyst_score")
    if not isinstance(output.get("why"), list) or not isinstance(output.get("risks"), list):
        reasons.append("missing_analyst_reason_and_risk")
    if status == "ANALYZED_INDICATIVE_SETUP":
        entry, stop, target = (
            output.get("entry_price"), output.get("lowest_sell_point"),
            output.get("sell_point")
        )
        if not all(_positive(v) for v in (entry, stop, target)) or not stop < entry < target:
            reasons.append("invalid_stop_and_target")
        else:
            calculated = 100 * (target / entry - 1)
            potential = output.get("potential_pct")
            if not _positive(potential) or abs(calculated - potential) > 0.1:
                reasons.append("potential_not_derived_from_target")
        if (not _positive(output.get("net_rr"))
                or output["net_rr"] < 2
                or not _positive(output.get("max_risk_sek"))
                or output["max_risk_sek"] > 0.01 * capital_sek + 0.02
                or not isinstance(output.get("quantity"), int)
                or isinstance(output.get("quantity"), bool)
                or output["quantity"] < 1
                or output.get("levels_status") != "ENDAST_PRELIMINÄRT_SCENARIO"):
            reasons.append("risk_or_price_level_not_approved")
    elif status in ("ANALYSIS_UNAVAILABLE", "ANALYZED_NO_VALID_SETUP"):
        if any(output.get(field) is not None for field in
               ("entry_price", "lowest_sell_point", "sell_point", "potential_pct")):
            reasons.append("invented_levels_on_unapproved_analysis")
    return reasons


def review_research_report(report, *, now=None, max_report_age_seconds=900,
                           max_article_age_seconds=86400):
    now = now or datetime.now(timezone.utc)
    if not isinstance(report, dict):
        raise ValueError("invalid_report")
    if (report.get("trade_signals_enabled") is not False
            or report.get("actionable_count") != 0):
        raise ValueError("report_attempts_trading")
    if not _fresh_timestamp(report.get("fetched_at_utc"), now, max_report_age_seconds):
        raise ValueError("report_is_stale_or_undated")
    capital = report.get("capital_sek", 15000)
    if (not _positive(capital) or not 10000 <= capital <= 25000):
        raise ValueError("invalid_research_capital")
    raw = report.get("research_candidates")
    if not isinstance(raw, list) or len(raw) > 100:
        raise ValueError("invalid_candidate_list")
    accepted, rejected, seen = [], [], set()
    for number, row in enumerate(raw):
        reasons = []
        if not isinstance(row, dict):
            rejected.append({"index": number, "reasons": ["invalid_row"]})
            continue
        if row.get("actionable") is not False or row.get("trade_signal") is not None:
            reasons.append("trading_claim")
        if row.get("publisher_isin_confirmed") is not False:
            reasons.append("unsupported_news_verification_claim")
        if row.get("timestamp_verified") is not False:
            reasons.append("unsupported_quote_freshness_claim")
        isin, ticker = row.get("isin"), row.get("ticker")
        if (not isinstance(isin, str) or len(isin) != 12
                or not isinstance(ticker, str) or not ticker.strip()
                or row.get("mic") != "XSTO"):
            reasons.append("invalid_instrument")
        if not isinstance(row.get("headline"), str) or not row["headline"].strip():
            reasons.append("missing_headline")
        if not _fresh_timestamp(row.get("published_at"), now, max_article_age_seconds):
            reasons.append("stale_article")
        url = row.get("news_url")
        host = urlsplit(url).hostname if isinstance(url, str) else None
        if not isinstance(url, str) or urlsplit(url).scheme != "https" or host not in TRUSTED_ARTICLE_DOMAINS:
            reasons.append("unapproved_article_source")
        score = row.get("research_score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not isfinite(score) or not 0 <= score <= 10:
            reasons.append("invalid_research_score")
        if (not isinstance(row.get("source"), str) or not row["source"].strip()):
            reasons.append("unknown_source")
        reasons.extend(_check_independent_analyst(row, capital_sek=capital))
        key = (isin, url)
        if key in seen:
            reasons.append("duplicate_article")
        seen.add(key)
        if reasons:
            rejected.append({"index": number, "reasons": reasons})
        else:
            accepted.append(row)
    return {
        "checked": len(raw),
        "accepted": accepted,
        "rejected": rejected,
        "all_checked": len(accepted) + len(rejected) == len(raw),
        "actionable_count": 0,
        "mode": "RESEARCH_ONLY",
    }
