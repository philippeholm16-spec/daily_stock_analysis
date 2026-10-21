"""Conservative automatic discovery of XSTO research candidates from RSS headlines.

Extraction is provisional: editorial headlines do NOT carry an issuer-confirmed
ISIN, and Avanza's search covers at most 50 results, not the full stock universe.
No execution, real-time, performance, or trading signal claims.
"""
import re
from datetime import datetime, timezone
from math import isfinite
from urllib.parse import urlsplit

from src.news_first_discovery import classify_catalyst
from src.news_company_research import validate_avanza_identity, prefix_matches


# Leading editorial words that are not issuer names.
NON_ISSUER_STARTS = frozenset({
    "två", "tre", "fyra", "nya", "negativa", "positiva", "storbanken",
    "förvaltaren", "analys", "krönika", "teknisk", "börsen", "marknaden",
    "så", "här", "nu", "efter", "inför", "idag", "morgonens", "rapport",
    "svenska", "den", "det", "stora", "musk", "flera", "bolaget",
})
CATALYST_WEIGHTS = {
    "guidance": 5,
    "report": 4,
    "corporate_action": 4,
    "order": 3,
    "financing": 2,
}


def extract_issuer_query(headline):
    """Propose one short search phrase, never assert that it is a company.

    Requires headline to start with capitalized word(s) and a nontrivial name.
    Handles 'SKF:s' by dropping Swedish possessive ':s'. Two initial
    capitalized words are used for multiword names like 'Inhalation Sciences'.
    """
    if not isinstance(headline, str):
        return None
    clean = headline.strip()
    match = re.match(r"^([A-ZÅÄÖ][\wÅÄÖåäö&.-]{2,})(?=\b|:)", clean)
    if not match:
        return None
    first = match.group(1).rstrip(".")
    if first.casefold() in NON_ISSUER_STARTS:
        return None
    remainder = clean[match.end():]
    if remainder.startswith(":s "):
        remainder = remainder[3:]
    if remainder.startswith(" "):
        second = re.match(r"^ ([A-ZÅÄÖ][\wÅÄÖåäö&.-]{2,})(?=\b|\s|:)", remainder)
        if second and second.group(1).casefold() not in {"B", "A", "AB", "VD"}:
            # Restrict obvious editorial capitalization and avoid long searches.
            return first + " " + second.group(1)
    return first


def select_headline_searches(items, *, now=None, max_age_hours=24, max_queries=8):
    """Bound search load. Only fresh items with recognized headline catalysts."""
    now = now or datetime.now(timezone.utc)
    queries, rejected, seen = [], [], set()
    for item in items:
        age = ((now - item.published_at).total_seconds() / 3600
               if item.published_at.tzinfo else -1)
        if age < 0 or age > max_age_hours:
            rejected.append({"headline": item.headline, "reason": "stale_or_invalid_date"})
            continue
        if not item.url.startswith("https://"):
            rejected.append({"headline": item.headline, "reason": "invalid_url"})
            continue
        catalysts = classify_catalyst(item.headline)
        if not catalysts:
            continue
        query = extract_issuer_query(item.headline)
        if not query:
            rejected.append({"headline": item.headline, "reason": "no_safe_prefix"})
            continue
        key = query.casefold()
        if key in seen:
            continue
        if len(queries) >= max_queries:
            rejected.append({"headline": item.headline, "reason": "query_budget_exceeded"})
            continue
        seen.add(key)
        queries.append({"query": query, "headline": item.headline,
                        "url": item.url, "published_at": item.published_at.isoformat(),
                        "source": item.source, "catalysts": catalysts})
    return queries, rejected


def _matches_issuer_title(headline, name, query):
    """Require whole query at start and company name starts with query.

    A matching prefix is useful for research but does not verify that the
    article concerns that ISIN. Different share classes stay ambiguous.
    """
    return prefix_matches(headline, query) and prefix_matches(name, query)


def assess_search_candidates(headline_item, search_hits, stock_info_by_id):
    """Reject ambiguous matches, non-XSTO listings and incomplete identities.

    Stock information is obtained independently with exact book IDs. Caller
    must obtain at most a bounded set of info calls.
    """
    query = headline_item["query"]
    matches, seen = [], set()
    for hit in search_hits:
        book_id = str(hit.get("order_book_id") or "")
        if not book_id.isascii() or not book_id.isdecimal() or book_id in seen:
            continue
        seen.add(book_id)
        if hit.get("exchange") != "Stockholmsbörsen":
            continue
        info = stock_info_by_id.get(book_id)
        identity = validate_avanza_identity(info, expected_book_id=book_id)
        if identity is None:
            continue
        if not _matches_issuer_title(headline_item["headline"], identity["stock_name"], query):
            continue
        matches.append(identity)
    if len(matches) != 1:
        return None, ("ambiguous_share_class" if len(matches) > 1
                      else "no_verified_xsto_identity")
    return matches[0], None


def rank_research_candidate(headline_item, identity, raw_quote, *, fetched_at=None):
    """Score catalyst, recency, and optional observed quote liquidity.

    Not relative-volume, momentum, RR or a trade signal. Provider delays and
    publisher name matching mean actionable is always False.
    """
    fetched_at = fetched_at or datetime.now(timezone.utc)
    age_hours = max(0, (fetched_at - datetime.fromisoformat(
        headline_item["published_at"])).total_seconds() / 3600)
    score = max((CATALYST_WEIGHTS.get(c, 0) for c in headline_item["catalysts"]), default=0)
    score += 2 if age_hours <= 3 else 1 if age_hours <= 12 else 0
    price = volume = spread_pct = turnover_proxy = None
    if isinstance(raw_quote, dict):
        last = raw_quote.get("last")
        vol = raw_quote.get("totalVolumeTraded")
        if (isinstance(last, (int, float)) and not isinstance(last, bool)
                and isfinite(last) and last > 0
                and isinstance(vol, (int, float)) and not isinstance(vol, bool)
                and isfinite(vol) and vol >= 0 and float(vol).is_integer()):
            price, volume = float(last), int(vol)
            turnover_proxy = price * volume
            # Low turnover can disqualify research priority, but not prove liquidity.
            if turnover_proxy >= 5_000_000:
                score += 1
            ask, bid = raw_quote.get("sell"), raw_quote.get("buy")
            if (isinstance(ask, (int, float)) and not isinstance(ask, bool)
                    and isinstance(bid, (int, float)) and not isinstance(bid, bool)
                    and isfinite(ask) and isfinite(bid) and ask >= bid > 0):
                spread_pct = round(100 * (ask - bid) / ((ask + bid) / 2), 4)
    return {
        **identity,
        "headline": headline_item["headline"],
        "news_url": headline_item["url"],
        "source": headline_item["source"],
        "published_at": headline_item["published_at"],
        "catalysts": headline_item["catalysts"],
        "research_score": score,
        "score_basis": "headline_catalyst_recency_and_turnover_proxy_only",
        "last_price": price,
        "volume": volume,
        "turnover_proxy_sek": round(turnover_proxy, 2) if turnover_proxy is not None else None,
        "spread_pct": spread_pct,
        "provider_is_real_time": raw_quote.get("isRealTime") is True if isinstance(raw_quote, dict) else False,
        "relative_volume": None,
        "intraday_momentum": None,
        "publisher_isin_confirmed": False,
        "timestamp_verified": False,
        "actionable": False,
        "trade_signal": None,
    }
