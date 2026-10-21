"""Strict company-news linking. This module does not fetch or invent news."""
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class NewsItem:
    source: str
    url: str
    headline: str
    published_at: datetime
    isin: str | None
    symbol: str | None
    verified_instrument: bool = False


def link_news(items, instruments, *, now=None, max_age_hours=48):
    """Link only explicit verified ISINs; ticker/headline-only matches are rejected.

    instruments: iterable of mappings containing isin, symbol and mic.
    Returns linked items and excluded items with reasons; no sentiment/trading signal.
    """
    now = now or datetime.now(timezone.utc)
    known = {i["isin"]: i for i in instruments if i.get("isin") and i.get("mic") == "XSTO"}
    linked, excluded = [], []
    for item in items:
        if not item.source or not item.url.startswith(("https://", "http://")) or not item.headline.strip():
            excluded.append((item, "missing_source_url_or_headline"))
        elif item.published_at.tzinfo is None or item.published_at > now or (now - item.published_at).total_seconds() > max_age_hours * 3600:
            excluded.append((item, "invalid_or_stale_publication_time"))
        elif not item.verified_instrument or not item.isin or item.isin not in known:
            excluded.append((item, "instrument_not_verified_by_isin"))
        elif item.symbol and item.symbol != known[item.isin]["symbol"]:
            excluded.append((item, "ticker_mismatch"))
        else:
            linked.append((known[item.isin], item))
    return linked, excluded
