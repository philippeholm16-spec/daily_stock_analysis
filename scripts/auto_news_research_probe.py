"""Live one-shot auto discovery: public Placera RSS -> Avanza search -> XSTO identity -> quote.

Read-only bounded diagnostics: one RSS request; max 12 text searches, at most
3 identity checks per query, at most 12 quote requests, 0 orders. Not a
complete Swedish market listing, and not verified issuer-news attribution.
"""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.avanza_mcp_bridge import unwrap
from scripts.public_rss_probe import ALLOWED_FEEDS, fetch_public_feed
from src.news_first_discovery import parse_news_feed
from src.automatic_news_candidates import (
    select_headline_searches, assess_search_candidates, rank_research_candidate,
)


async def run(*, max_queries=12, delay_seconds=0.6):
    if not 1 <= max_queries <= 12:
        raise ValueError("max_queries_out_of_bounds")
    if not 0.5 <= delay_seconds <= 10:
        raise ValueError("delay_seconds_out_of_bounds")
    fetched_at = datetime.now(timezone.utc)
    payload = fetch_public_feed(ALLOWED_FEEDS["placera"])
    items, feed_errors = parse_news_feed(payload, source="Placera",
                                          verified_isin_field=False, max_items=40)
    search_items, exclusions = select_headline_searches(
        items, now=fetched_at, max_queries=max_queries)
    candidates, rejected = [], []
    stats = {"search_requests": 0, "identity_requests": 0,
             "quote_requests": 0, "matched": 0, "search_error": 0}
    from fastmcp import Client
    from avanza_mcp import mcp
    async with Client(mcp) as client:
        for news in search_items:
            try:
                found = unwrap(await client.call_tool("search_instruments", {
                    "query": news["query"], "instrument_type": "stock", "limit": 10
                }))
                stats["search_requests"] += 1
                hits = found.get("hits", [])
                if not isinstance(hits, list) or len(hits) > 3:
                    rejected.append({"query": news["query"], "reason": "too_many_search_hits"})
                    continue
                # Search may be incomplete; do not accept results if provider
                # itself declares candidates beyond the returned set.
                total = found.get("totalNumberOfHits")
                if isinstance(total, int) and total > len(hits):
                    rejected.append({"query": news["query"], "reason": "search_coverage_incomplete"})
                    continue
                stock_infos = {}
                for hit in hits:
                    book = str(hit.get("order_book_id") or "")
                    if not book.isascii() or not book.isdecimal():
                        continue
                    if hit.get("exchange") != "Stockholmsbörsen":
                        continue
                    try:
                        await asyncio.sleep(delay_seconds)
                        stock_infos[book] = unwrap(await client.call_tool(
                            "get_stock_info", {"order_book_id": book}))
                        stats["identity_requests"] += 1
                    except Exception:
                        rejected.append({"query": news["query"], "reason": "identity_lookup_failed"})
                identity, reason = assess_search_candidates(news, hits, stock_infos)
                if identity is None:
                    rejected.append({"query": news["query"], "reason": reason})
                    continue
                await asyncio.sleep(delay_seconds)
                stats["quote_requests"] += 1
                raw_quote = unwrap(await client.call_tool(
                    "get_stock_quote", {"order_book_id": identity["order_book_id"]}))
                row = rank_research_candidate(
                    news, identity, raw_quote, fetched_at=fetched_at)
                candidates.append(row)
                stats["matched"] += 1
            except Exception as exc:
                stats["search_error"] += 1
                rejected.append({"query": news["query"],
                                 "reason": "provider_error_" + type(exc).__name__})
            finally:
                await asyncio.sleep(delay_seconds)
    candidates.sort(key=lambda row: (-row["research_score"], row["ticker"]))
    return {
        "source": "Placera public RSS + unofficial Avanza MCP",
        "fetched_at_utc": fetched_at.isoformat(),
        "market_scope": "bounded news-driven sample; NOT full XSTO coverage",
        "news_items_parsed": len(items),
        "news_items_invalid": len(feed_errors),
        "headlines_queued": len(search_items),
        "presearch_rejections": exclusions,
        "provider_rejections": rejected,
        "metrics": stats,
        "research_candidates": candidates,
        "ranking": "catalyst/recency/observed price-volume proxy; NOT validated momentum or relative volume",
        "publisher_isin_verified": False,
        "quote_freshness_verified": False,
        "trade_signals_enabled": False,
        "actionable_count": 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("auto_news_research.json"))
    parser.add_argument("--max-queries", type=int, default=12)
    parser.add_argument("--delay-seconds", type=float, default=0.6)
    args = parser.parse_args()
    report = asyncio.run(run(max_queries=args.max_queries,
                              delay_seconds=args.delay_seconds))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
