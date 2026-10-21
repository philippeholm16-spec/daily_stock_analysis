"""One-shot research pipeline: Placera RSS -> checked Avanza stock info -> quotes.

This is *not* news attribution by ISIN, and NOT a trading signal.
One public RSS request and three specified public instrument IDs only.
"""
import asyncio
import json
from datetime import datetime, timezone

from scripts.avanza_mcp_bridge import unwrap
from scripts.public_rss_probe import ALLOWED_FEEDS, fetch_public_feed
from src.news_company_research import validate_avanza_identity, match_research_headlines
from src.news_first_discovery import parse_news_feed

# Verified by live search diagnostics on 2026-10-21; re-check each ID via
# get_stock_info at execution time. Third ID demonstrates First North exclusion.
PROBES = (
    ("290011", "Bulten"),
    ("233288", "Byggmax"),
    ("919077", "Incoax"),
)


async def run():
    fetched_at = datetime.now(timezone.utc)
    data = fetch_public_feed(ALLOWED_FEEDS["placera"])
    items, bad = parse_news_feed(data, source="Placera",
                                 verified_isin_field=False, max_items=40)
    identities, quotes, aliases, rejected = {}, {}, {}, []
    from fastmcp import Client
    from avanza_mcp import mcp
    async with Client(mcp) as client:
        for book_id, company_alias in PROBES:
            try:
                raw = unwrap(await client.call_tool(
                    "get_stock_info", {"order_book_id": book_id}))
                identity = validate_avanza_identity(raw, expected_book_id=book_id)
                if identity is None:
                    rejected.append({"book_id": book_id,
                                     "reason": "unverified_XSTO_identity"})
                    continue
                identities[book_id] = identity
                aliases[book_id] = company_alias
                raw_quote = unwrap(await client.call_tool(
                    "get_stock_quote", {"order_book_id": book_id}))
                quotes[book_id] = raw_quote
            except Exception as exc:
                rejected.append({"book_id": book_id,
                                 "reason": "provider_error_" + type(exc).__name__})
    output = match_research_headlines(items, identities, aliases, quotes,
                                      now=fetched_at)
    # Report only five most recent matched research rows, not a market-wide ranking.
    output["candidates"] = output["candidates"][:5]
    output.update({
        "source": "Placera RSS + unofficial Avanza MCP",
        "run_time": fetched_at.isoformat(),
        "rss_items_parsed": len(items),
        "rss_items_rejected": len(bad),
        "instruments_checked": len(PROBES),
        "xsto_verified": len(identities),
        "excluded_instruments": rejected,
        "market_scope": "3 named candidates, NOT complete Stockholm market",
        "publisher_isin_attribution": "unverified; publisher headlines matched by name only",
        "trade_signals_enabled": False,
    })
    return output


def main():
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
