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
from src.google_swedish_news import collect_google_news
from src.news_source_diversity import select_diverse_searches
from src.stockholm_stock_analyst import analyze_xsto_candidate
from src.automatic_news_candidates import (
    select_headline_searches, assess_search_candidates, rank_research_candidate,
)


async def run(*, max_queries=12, delay_seconds=0.6, include_google_news=True,
              capital_sek=15000):
    if not 1 <= max_queries <= 12:
        raise ValueError("max_queries_out_of_bounds")
    if not 0.5 <= delay_seconds <= 10:
        raise ValueError("delay_seconds_out_of_bounds")
    if isinstance(capital_sek, bool) or not isinstance(capital_sek, (int, float)) or not 10000 <= capital_sek <= 25000:
        raise ValueError("capital_sek_must_be_between_10000_and_25000")
    fetched_at = datetime.now(timezone.utc)
    payload = fetch_public_feed(ALLOWED_FEEDS["placera"])
    items, feed_errors = parse_news_feed(payload, source="Placera",
                                          verified_isin_field=False, max_items=40)
    google = {"news_items": [], "errors": [], "groups": {}}
    if include_google_news:
        google = collect_google_news(now=fetched_at)
    # Prioritize direct publisher RSS; augment with Google News index headlines.
    # News matched from either source remains provisional and research-only.
    search_items, exclusions, source_counts = select_diverse_searches(
        items, google["news_items"], now=fetched_at, max_queries=max_queries)
    candidates, rejected = [], []
    stats = {"search_requests": 0, "identity_requests": 0,
             "quote_requests": 0, "chart_requests": 0,
             "matched": 0, "analysis_attempted": 0, "analysis_completed": 0,
             "search_error": 0}
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
                # Every verified discovered instrument gets its OWN independent
                # Stock Analyst assessment, even when pricing/history fails.
                await asyncio.sleep(delay_seconds)
                raw_quote = {}
                try:
                    stats["quote_requests"] += 1
                    raw_quote = unwrap(await client.call_tool(
                        "get_stock_quote", {"order_book_id": identity["order_book_id"]}))
                except Exception:
                    rejected.append({"query": news["query"], "reason": "quote_lookup_failed"})
                row = rank_research_candidate(
                    news, identity, raw_quote, fetched_at=fetched_at)
                raw_chart = None
                try:
                    await asyncio.sleep(delay_seconds)
                    stats["chart_requests"] += 1
                    first_page = unwrap(await client.call_tool(
                        "get_stock_chart", {
                            "order_book_id": identity["order_book_id"],
                            "time_period": "one_week", "offset": 0, "limit": 100
                        }))
                    pagination = first_page.get("pagination") or {}
                    total_bars = pagination.get("total")
                    if isinstance(total_bars, int) and total_bars >= 25 and total_bars <= 2000:
                        if total_bars <= 100:
                            raw_chart = first_page
                        else:
                            await asyncio.sleep(delay_seconds)
                            stats["chart_requests"] += 1
                            raw_chart = unwrap(await client.call_tool(
                                "get_stock_chart", {
                                    "order_book_id": identity["order_book_id"],
                                    "time_period": "one_week",
                                    "offset": total_bars - 80, "limit": 80
                                }))
                except Exception:
                    rejected.append({"query": news["query"], "reason": "chart_lookup_failed"})
                stats["analysis_attempted"] += 1
                result = analyze_xsto_candidate(row, raw_chart, now=fetched_at,
                                                 capital_sek=capital_sek)
                row["stock_analyst"] = result
                if result["status"] != "ANALYSIS_UNAVAILABLE":
                    stats["analysis_completed"] += 1
                candidates.append(row)
                stats["matched"] += 1
            except Exception as exc:
                stats["search_error"] += 1
                rejected.append({"query": news["query"],
                                 "reason": "provider_error_" + type(exc).__name__})
            finally:
                await asyncio.sleep(delay_seconds)
    candidates.sort(key=lambda row: (
        -float(row["stock_analyst"]["score"] or 0),
        row["ticker"]
    ))
    return {
        "source": "Placera public RSS + unofficial Avanza MCP",
        "fetched_at_utc": fetched_at.isoformat(),
        "capital_sek": capital_sek,
        "market_scope": "bounded news-driven sample; NOT full XSTO coverage",
        "news_items_parsed": len(items),
        "google_news_items": len(google["news_items"]),
        "google_news_groups": google["groups"],
        "google_news_errors": google["errors"],
        "news_items_invalid": len(feed_errors),
        "headlines_queued": len(search_items),
        "source_query_counts": source_counts,
        "presearch_rejections": exclusions,
        "provider_rejections": rejected,
        "metrics": stats,
        "research_candidates": candidates,
        "ranking": "Stock Analyst Sweden independent technical score; press discovery priority is NOT a recommendation",
        "analysis_coverage": {"verified_candidates": len(candidates),
                              "analyzed_or_explicitly_unavailable": sum(
                                  isinstance(row.get("stock_analyst"), dict)
                                  for row in candidates),
                              "source_opinions_used_in_analysis": False},
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
    parser.add_argument("--no-google-news", action="store_true")
    parser.add_argument("--capital-sek", type=float, default=15000)
    args = parser.parse_args()
    report = asyncio.run(run(max_queries=args.max_queries,
                              delay_seconds=args.delay_seconds,
                              include_google_news=not args.no_google_news,
                              capital_sek=args.capital_sek))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
