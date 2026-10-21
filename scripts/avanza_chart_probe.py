"""Probe two public stock charts without storing entire provider payloads."""
import asyncio
import json
from scripts.avanza_mcp_bridge import unwrap


async def main():
    from avanza_mcp import mcp
    from fastmcp import Client
    report = []
    async with Client(mcp) as client:
        for period in ("one_week", "one_month"):
            try:
                raw = unwrap(await client.call_tool("get_stock_chart", {
                    "order_book_id": "290011", "time_period": period,
                    "offset": 0, "limit": 100
                }))
                data = raw.get("data") or {}
                rows = data.get("ohlc") or []
                meta = data.get("metadata") or {}
                report.append({
                    "period": period,
                    "count": len(rows),
                    "pagination": raw.get("pagination"),
                    "metadata": meta,
                    "first": rows[0] if rows else None,
                    "last": rows[-1] if rows else None,
                    "actionable": False,
                })
            except Exception as exc:
                report.append({"period": period, "error": type(exc).__name__,
                               "actionable": False})
    print(json.dumps({"book_id": "290011", "charts": report}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
