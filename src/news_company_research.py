"""Research-only publisher-headline to Avanza stock matching.

Only use exact headline-start names and exact Avanza book IDs with verified
XSTO listings. A headline match is NOT an issuer-confirmed ISIN news event.
Never silently upgrade a journalistic name mention to verified issuer news.
"""
import re
from datetime import datetime, timezone
from math import isfinite


def validate_avanza_identity(info, *, expected_book_id):
    """Return identity only when provider explicitly confirms XSTO + ISIN."""
    if not isinstance(info, dict):
        return None
    listing = info.get("listing")
    if not isinstance(listing, dict):
        return None
    isin = info.get("isin")
    if (str(info.get("orderbookId")) != str(expected_book_id)
            or not str(expected_book_id).isdigit()
            or not isinstance(isin, str)
            or not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{10}", isin)
            or listing.get("marketPlaceCode") != "XSTO"
            or listing.get("currency") != "SEK"
            or not listing.get("tickerSymbol")
            or not isinstance(info.get("name"), str)):
        return None
    return {
        "isin": isin,
        "order_book_id": str(expected_book_id),
        "ticker": listing["tickerSymbol"],
        "stock_name": info["name"],
        "mic": "XSTO",
        "identity_source": "avanza_get_stock_info",
    }


def prefix_matches(headline, name):
    """Only exact name at headline start; never partial words or substring."""
    if not isinstance(headline, str) or not isinstance(name, str):
        return False
    candidate = name.strip()
    if len(candidate) < 4:
        return False
    h = headline.lstrip().casefold()
    n = candidate.casefold()
    return bool(re.match(r"^" + re.escape(n) + r"(?=$|[\s:;,.!?–—-])", h))


def match_research_headlines(news, identities, aliases, quotes, *, now=None,
                             max_age_hours=24):
    """Match provider identities to publisher mentions, no trading inference.

    aliases maps order_book_id -> editorial company name approved for this
    diagnostic. Ambiguous names rejected. Quotes are raw provider dictionaries.
    """
    now = now or datetime.now(timezone.utc)
    rows, seen = [], set()
    counters = {"unmatched": 0, "ambiguous": 0, "stale": 0,
                "quote_unavailable": 0, "matched": 0}
    for item in news:
        if item.published_at.tzinfo is None:
            counters["stale"] += 1
            continue
        age = (now - item.published_at).total_seconds()
        if age < 0 or age > max_age_hours * 3600:
            counters["stale"] += 1
            continue
        candidates = []
        for book_id, ident in identities.items():
            if not ident or book_id not in aliases:
                continue
            if prefix_matches(item.headline, aliases[book_id]):
                candidates.append(ident)
        if len(candidates) != 1:
            counters["ambiguous" if len(candidates) > 1 else "unmatched"] += 1
            continue
        matched = candidates[0]
        unique_key = (matched["isin"], item.url)
        if unique_key in seen:
            continue
        seen.add(unique_key)
        quote = quotes.get(matched["order_book_id"])
        price, volume = None, None
        if isinstance(quote, dict):
            price = quote.get("last")
            volume = quote.get("totalVolumeTraded")
        valid = (isinstance(price, (int, float)) and not isinstance(price, bool)
                 and isfinite(price) and price > 0
                 and isinstance(volume, (int, float)) and not isinstance(volume, bool)
                 and isfinite(volume) and volume >= 0
                 and float(volume).is_integer())
        if not valid:
            counters["quote_unavailable"] += 1
        counters["matched"] += 1
        rows.append({
            **matched,
            "headline": item.headline,
            "published_at": item.published_at.isoformat(),
            "source": item.source,
            "news_url": item.url,
            "matched_by": "exact_company_name_at_headline_start",
            "publisher_isin_confirmed": False,
            "last_price": float(price) if valid else None,
            "volume": int(volume) if valid else None,
            "quote_is_real_time": quote.get("isRealTime") is True if valid else False,
            "timestamp_verified": False,
            "actionable": False,
            "status": "RESEARCH_ONLY_UNVERIFIED_NEWS_IDENTITY",
        })
    rows.sort(key=lambda x: x["published_at"], reverse=True)
    return {"candidates": rows, "coverage": counters, "actionable_count": 0}
