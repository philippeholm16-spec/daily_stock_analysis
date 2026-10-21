"""Non-actionable headline watchlist from a public news feed.

No guessed ticker, no invented ISIN, no orders. Priority only determines
which headlines should be researched first.
"""
from datetime import datetime, timezone
from urllib.parse import urlsplit

from src.news_first_discovery import classify_catalyst


def build_headline_watchlist(items, *, now=None, max_age_hours=24):
    now = now or datetime.now(timezone.utc)
    seen = set()
    rows = []
    for item in items:
        if not item.headline or not item.url or urlsplit(item.url).scheme != "https":
            continue
        if item.published_at.tzinfo is None:
            continue
        age_hours = (now - item.published_at).total_seconds() / 3600
        if age_hours < 0 or age_hours > max_age_hours:
            continue
        key = item.url.rstrip("/").casefold()
        if key in seen:
            continue
        seen.add(key)
        catalysts = classify_catalyst(item.headline)
        if not catalysts:
            continue
        rows.append({
            "headline": item.headline,
            "url": item.url,
            "source": item.source,
            "published_at": item.published_at.isoformat(),
            "catalysts": catalysts,
            "priority": min(5, len(catalysts) * 2 + (1 if age_hours <= 3 else 0)),
            "instrument_status": "UNVERIFIED",
            "actionable": False,
        })
    return sorted(rows, key=lambda x: (-x["priority"], x["published_at"], x["url"]))
