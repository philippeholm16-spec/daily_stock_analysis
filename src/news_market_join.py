"""Join trusted issuer news to a verified XSTO listing and data-only quote.

This is research enrichment, never an executable trade recommendation.
A publisher headline alone does not establish ISIN or share class.
"""
from math import isfinite

from src.swedish_stock_news import link_news


def enrich_news_with_quotes(news, instruments, quotes_by_isin, *, now=None):
    """quotes_by_isin: {ISIN: {last_price, volume, is_real_time}}.

    Only verified ISIN-matched news can enter the enriched list.
    Prices must be finite positive numbers, volumes nonnegative integers.
    Delayed quotes remain data-only; no actionable output is produced.
    """
    linked, excluded = link_news(news, instruments, now=now)
    results = []
    missing = 0
    invalid = 0
    for instrument, item in linked:
        quote = quotes_by_isin.get(instrument["isin"])
        if not isinstance(quote, dict):
            missing += 1
            continue
        price = quote.get("last_price")
        volume = quote.get("volume")
        if (isinstance(price, bool) or not isinstance(price, (int, float))
                or not isfinite(price) or price <= 0
                or isinstance(volume, bool) or not isinstance(volume, int)
                or volume < 0):
            invalid += 1
            continue
        results.append({
            "isin": instrument["isin"],
            "symbol": instrument["symbol"],
            "headline": item.headline,
            "news_source": item.source,
            "news_url": item.url,
            "published_at": item.published_at.isoformat(),
            "last_price": float(price),
            "volume": volume,
            "provider_is_real_time": quote.get("is_real_time") is True,
            "market_data_verified": False,
            "actionable": False,
            "status": "DATA_ONLY_IDENTITY_LINKED",
        })
    return {"matched": results, "unverified_news": len(excluded),
            "missing_quotes": missing, "invalid_quotes": invalid,
            "actionable_count": 0}
