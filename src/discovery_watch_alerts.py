"""Select Telegram discovery alerts only AFTER independent per-stock review.

Score is the 0-10 news/volume DISCOVERY priority, not Stock Analyst's 0-100
technical score or a buy recommendation. A score of exactly 6 is NOT >6.
Deduplicate each instrument per run; report all filtered/rejected entries.
"""
from datetime import datetime


def select_watch_alerts(review, *, min_score_exclusive=6):
    if (not isinstance(review, dict) or review.get("mode") != "RESEARCH_ONLY"
            or review.get("all_checked") is not True
            or review.get("actionable_count") != 0
            or not isinstance(review.get("accepted"), list)
            or not isinstance(review.get("rejected"), list)):
        raise ValueError("independent_research_review_required")
    if (isinstance(min_score_exclusive, bool)
            or not isinstance(min_score_exclusive, (int, float))
            or not 0 <= min_score_exclusive < 10):
        raise ValueError("invalid_discovery_alert_threshold")
    chosen = {}
    below = []
    for candidate in review["accepted"]:
        score = candidate.get("discovery_priority")
        if (isinstance(score, bool)
                or not isinstance(score, (float, int))
                or not 0 <= score <= 10):
            raise ValueError("invalid_discovery_priority_after_review")
        if score <= min_score_exclusive:
            below.append(candidate)
            continue
        identity = candidate["isin"]
        # Same share from two different news headlines: only one alert. Prefer
        # highest discovery priority; timestamps break ties deterministically.
        prior = chosen.get(identity)
        if prior is None or (score, candidate["published_at"], candidate["news_url"]) > (
                prior["discovery_priority"], prior["published_at"], prior["news_url"]):
            chosen[identity] = candidate
    selected = sorted(chosen.values(), key=lambda r: (
        -r["discovery_priority"],
        -float(r["stock_analyst"].get("score") or 0),
        r["ticker"]
    ))
    return {
        **review,
        "accepted": selected,
        # This is a delivery FILTER, not a new independent approval mechanism.
        "reviewed_and_valid": len(review["accepted"]),
        "below_threshold_count": len(below),
        "duplicate_ticker_count": len(review["accepted"]) - len(below) - len(selected),
        "alert_threshold_exclusive": min_score_exclusive,
        "alert_count": len(selected),
        "delivery_type": "NEWS_DISCOVERY_WATCH",
        "all_checked": True,
        "actionable_count": 0,
    }
