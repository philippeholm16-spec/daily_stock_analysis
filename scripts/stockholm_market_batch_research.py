"""Review a verified subset of ALL Nasdaq Stockholm stocks, not only news picks.

Reads an independently authorized complete XSTO listing and exact Avanza
order-book mapping. Limit 12 stocks/run, sequential requests with delay. Every
verified stock receives independent technical analysis or explicit unavailable
status; no Telegram notifications or orders in this module.
"""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from math import isfinite

from scripts.avanza_mcp_bridge import unwrap
from scripts.avanza_full_market import load_manifest
from src.stockholm_universe_batch import create_batch_plan
from src.news_company_research import validate_avanza_identity
from src.stockholm_stock_analyst import analyze_xsto_candidate


async def scan_batch(plan, call_tool, *, now, capital_sek=15000,
                     delay_seconds=1.0, sleep=asyncio.sleep):
    if not 1 <= delay_seconds <= 20:
        raise ValueError("invalid_provider_delay")
    if not 10000 <= capital_sek <= 25000:
        raise ValueError("invalid_trading_capital")
    records = []
    requests = 0

    async def request(name, data):
        nonlocal requests
        await sleep(delay_seconds)
        requests += 1
        return await call_tool(name, data)

    for row in plan.stocks:
        book = row["order_book_id"]
        output = {
            "isin": row["isin"], "ticker": row["symbol"],
            "order_book_id": book, "segment": row["segment"],
            "reviewed": False, "actionable": False,
        }
        try:
            info = await request("get_stock_info", {"order_book_id": book})
            identity = validate_avanza_identity(info, expected_book_id=book)
            if (identity is None or identity["isin"] != row["isin"]
                    or identity["ticker"] != row["symbol"]):
                raise ValueError("independent_stock_identity_mismatch")
            raw = await request("get_stock_quote", {"order_book_id": book})
            last, volume = raw.get("last"), raw.get("totalVolumeTraded")
            if (not isinstance(last, (float, int)) or isinstance(last, bool)
                    or not isfinite(last) or last <= 0
                    or not isinstance(volume, (float, int)) or isinstance(volume, bool)
                    or not isfinite(volume) or volume < 0):
                raise ValueError("invalid_public_quote")
            turnover = raw.get("totalValueTraded")
            turnover = (float(turnover) if isinstance(turnover, (float, int))
                        and not isinstance(turnover, bool) and isfinite(turnover)
                        and turnover >= 0 else float(last * volume))
            ask, bid = raw.get("sell"), raw.get("buy")
            spread_pct = (
                round(100*(ask-bid)/((ask+bid)/2), 4)
                if isinstance(ask, (float, int)) and not isinstance(ask, bool)
                and isinstance(bid, (float, int)) and not isinstance(bid, bool)
                and isfinite(ask) and isfinite(bid) and ask >= bid > 0
                else None
            )
            chart = None
            try:
                first = await request("get_stock_chart", {
                    "order_book_id": book, "time_period": "one_week",
                    "offset": 0, "limit": 100
                })
                paging = first.get("pagination") or {}
                total = paging.get("total")
                if isinstance(total, int) and 25 <= total <= 2000:
                    if total <= 100:
                        chart = first
                    else:
                        chart = await request("get_stock_chart", {
                            "order_book_id": book, "time_period": "one_week",
                            "offset": total-80, "limit": 80
                        })
            except Exception:
                # A verified stock stays in the coverage report. No chart
                # means explicit unavailable analysis, never a forged setup.
                chart = None
            analysis = analyze_xsto_candidate({
                **identity,
                "last_price": last, "turnover_proxy_sek": turnover,
                "spread_pct": spread_pct
            }, chart, now=now, capital_sek=capital_sek)
            output.update(
                reviewed=True, status="ANALYZED_OR_EXPLICIT_UNAVAILABLE",
                quote_is_real_time_reported=raw.get("isRealTime") is True,
                stock_analyst=analysis
            )
        except Exception as exc:
            output.update(status="REJECTED", reason=type(exc).__name__,
                          reviewed=False)
        records.append(output)
    return {
        "batch_index": plan.batch_index,
        "batch_count": plan.batch_count,
        "batch_size": plan.batch_size,
        "reference_hash": plan.reference_hash,
        "reference_id_coverage_verified": plan.complete_reference_audit,
        "entire_stockholm_price_scan_completed": False,
        "stock_count_main_market": plan.total_stocks,
        "provider_requests": requests,
        "stocks_reviewed_or_explicitly_unavailable": sum(r["reviewed"] for r in records),
        "stocks_rejected": sum(not r["reviewed"] for r in records),
        "very_good_indicative_setups": sum(
            r.get("stock_analyst", {}).get("opportunity_grade") == "VERY_GOOD"
            for r in records
        ),
        "source": "unofficial read-only Avanza public stock data",
        "no_orders": True, "actionable_count": 0,
        "results": records,
    }


async def _run_live(plan, *, capital_sek=15000, delay_seconds=1.0):
    from fastmcp import Client
    from avanza_mcp import mcp
    async with Client(mcp) as client:
        async def fetch(name, args):
            return unwrap(await client.call_tool(name, args))
        return await scan_batch(
            plan, fetch, now=datetime.now(timezone.utc),
            capital_sek=capital_sek, delay_seconds=delay_seconds
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--batch-index", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--capital-sek", type=float, default=15000)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=Path("market_batch_research.json"))
    args = parser.parse_args()
    _, rows = load_manifest(args.mapping)
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    plan = create_batch_plan(reference, mapping, index=args.batch_index,
                             size=args.batch_size)
    report = asyncio.run(_run_live(plan, capital_sek=args.capital_sek,
                                    delay_seconds=args.delay_seconds))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
