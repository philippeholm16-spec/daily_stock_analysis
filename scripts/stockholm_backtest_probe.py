"""Small *exploratory* historical Avanza walk-forward diagnostic on Bulten.

Never treat one stock/week as accuracy validation. One read-only identity
request plus <=3 rate-limited chart pages, no account data and no orders.
Historical bars remain in memory; report only aggregated research metrics.
"""
import asyncio
import json
from datetime import datetime, timezone

from scripts.avanza_mcp_bridge import unwrap
from src.news_company_research import validate_avanza_identity
from src.stockholm_walkforward import walk_forward_replay

BOOK_ID = "290011"
PAGE_SIZE = 100
MAX_TOTAL = 300


def decode_page(payload, *, offset, expected_total=None):
    meta = payload.get("pagination") or {}
    data = payload.get("data") or {}
    rows = data.get("ohlc")
    resolution = ((data.get("metadata") or {}).get("resolution") or {}).get("chartResolution")
    total = meta.get("total")
    if (resolution != "ten_minutes" or not isinstance(rows, list)
            or not isinstance(total, int) or not 50 <= total <= MAX_TOTAL
            or total != expected_total and expected_total is not None
            or meta.get("offset") != offset
            or meta.get("returned") != len(rows)
            or len(rows) > PAGE_SIZE):
        raise ValueError("invalid_or_truncated_historical_page")
    result = []
    for bar in rows:
        timestamp = bar.get("timestamp")
        if not isinstance(timestamp, int) or not 1_500_000_000_000 <= timestamp <= 4_000_000_000_000:
            raise ValueError("invalid_chart_timestamp")
        stamp = datetime.fromtimestamp(timestamp/1000, tz=timezone.utc)
        low, high, start, end = (
            bar.get("low"), bar.get("high"), bar.get("open"), bar.get("close")
        )
        volume = bar.get("totalVolumeTraded")
        if (not all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0
                    for x in (low, high, start, end))
                or not low <= min(start, end) <= max(start, end) <= high
                or not isinstance(volume, (int, float)) or isinstance(volume, bool)
                or volume < 0):
            raise ValueError("invalid_ohlc_price_or_volume")
        result.append({
            "at": stamp, "open": start, "high": high, "low": low,
            "close": end, "volume": volume
        })
    return total, result


async def main():
    from avanza_mcp import mcp
    from fastmcp import Client

    async with Client(mcp) as client:
        raw = unwrap(await client.call_tool("get_stock_info", {
            "order_book_id": BOOK_ID
        }))
        identity = validate_avanza_identity(raw, expected_book_id=BOOK_ID)
        if identity is None or identity["ticker"] != "BULTEN":
            raise RuntimeError("missing_verified_bulten_identity")
        pages, all_rows, total = 0, [], None
        while total is None or len(all_rows) < total:
            if pages >= 3:
                raise RuntimeError("historical_scan_page_limit_exceeded")
            offset = len(all_rows)
            await asyncio.sleep(1.0)
            payload = unwrap(await client.call_tool("get_stock_chart", {
                "order_book_id": BOOK_ID, "time_period": "one_week",
                "offset": offset, "limit": PAGE_SIZE
            }))
            total, rows = decode_page(payload, offset=offset, expected_total=total)
            if not rows:
                raise RuntimeError("empty_chart_page")
            all_rows.extend(rows)
            pages += 1
    if len(all_rows) != total:
        raise RuntimeError("incomplete_historical_chart")
    if any(all_rows[i]["at"] <= all_rows[i-1]["at"] for i in range(1, len(all_rows))):
        raise RuntimeError("unsorted_historical_chart")
    result = walk_forward_replay(
        all_rows, isin=identity["isin"], ticker=identity["ticker"],
        lookback=50, horizon=12, step=12,
        spread_pct=0.10, per_share_spread=0.02,
        slippage=0.02, commission=1.0
    )
    result["provider"] = "Unofficial public Avanza MCP"
    result["period"] = "one_week"
    result["provider_chart_pages"] = pages
    result["comparison_ready"] = False
    result["actual_market_spreads_unknown"] = True
    result["out_of_sample_verified"] = False
    print(json.dumps({k: v for k, v in result.items() if k != "trades"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
