"""Telegram research alerts require Stock Analyst's own VERY GOOD opportunity.

Publisher discovery priority is never part of eligibility or ranking.
All candidates first pass independent per-item review. Missing/no valid
stop/target, stale data or a lower stock score means no push notification.
No trading is authorized by this research-only filter.
"""
from math import isfinite


def select_watch_alerts(review, *, min_analyst_score=85):
    if (not isinstance(review, dict) or review.get("mode") != "RESEARCH_ONLY"
            or review.get("all_checked") is not True
            or review.get("actionable_count") != 0
            or not isinstance(review.get("accepted"), list)
            or not isinstance(review.get("rejected"), list)):
        raise ValueError("independent_research_review_required")
    if (isinstance(min_analyst_score, bool)
            or not isinstance(min_analyst_score, (int, float))
            or not isfinite(min_analyst_score)
            or not 80 <= min_analyst_score <= 100):
        raise ValueError("invalid_independent_score_threshold")
    by_isin = {}
    not_very_good = 0
    for row in review["accepted"]:
        a = row.get("stock_analyst") or {}
        score = a.get("score")
        qualified = (
            isinstance(score, (int, float)) and not isinstance(score, bool)
            and isfinite(score) and score >= min_analyst_score
            and a.get("status") == "ANALYZED_INDICATIVE_SETUP"
            and a.get("opportunity_grade") == "VERY_GOOD"
            and a.get("source_news_opinion_used") is False
            and a.get("actionable") is False
            and isinstance(a.get("net_rr"), (int, float))
            and not isinstance(a["net_rr"], bool) and a["net_rr"] >= 2.0
            and isinstance(a.get("potential_pct"), (int, float))
            and not isinstance(a["potential_pct"], bool)
            and a["potential_pct"] >= 3.0
        )
        if not qualified:
            not_very_good += 1
            continue
        isin = row["isin"]
        old = by_isin.get(isin)
        if old is None or (
            score, a["net_rr"], row["published_at"], row["news_url"]
        ) > (
            old["stock_analyst"]["score"],
            old["stock_analyst"]["net_rr"],
            old["published_at"], old["news_url"]
        ):
            by_isin[isin] = row
    ordered = sorted(by_isin.values(), key=lambda row: (
        -row["stock_analyst"]["score"],
        -row["stock_analyst"]["net_rr"],
        row["ticker"]
    ))
    return {
        **review,
        "accepted": ordered,
        "reviewed_and_valid": len(review["accepted"]),
        "below_threshold_count": not_very_good,
        "duplicate_ticker_count": len(review["accepted"]) - not_very_good - len(ordered),
        "min_independent_analyst_score": min_analyst_score,
        "alert_count": len(ordered),
        "delivery_type": "VERY_GOOD_STOCK_ANALYST_RESEARCH",
        "all_checked": True,
        "actionable_count": 0,
    }
