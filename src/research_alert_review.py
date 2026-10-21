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
