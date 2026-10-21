"""Public Avanza identity diagnostics: explicit candidates, no trades."""
import asyncio
import json

from scripts.avanza_mcp_bridge import unwrap


async def run():
    from fastmcp import Client
    from avanza_mcp import mcp
    out = []
    async with Client(mcp) as client:
        for query in ("Bulten", "Byggmax", "Incoax"):
            try:
                search = unwrap(await client.call_tool("search_instruments", {
                    "query": query, "instrument_type": "stock", "limit": 10
                }))
                candidates = [
                    {"name": h.get("name"), "order_book_id": h.get("order_book_id"),
                     "isin": h.get("isin"), "exchange": h.get("exchange")}
                    for h in search.get("hits", [])
                ]
                out.append({"query": query, "candidates": candidates})
            except Exception as exc:
                out.append({"query": query, "error": type(exc).__name__})
        info = []
        for book_id in ("5269", "1296604"):
            try:
                raw = unwrap(await client.call_tool("get_stock_info",
                                                    {"order_book_id": book_id}))
                listing = raw.get("listing") or {}
                company = raw.get("company") or {}
                info.append({
                    "requested_book_id": book_id,
                    "returned_book_id": raw.get("orderbookId"),
                    "stock_name": raw.get("name"),
                    "isin": raw.get("isin"),
                    "ticker": listing.get("tickerSymbol"),
                    "short_name": listing.get("shortName"),
                    "currency": listing.get("currency"),
                    "market_code": listing.get("marketPlaceCode"),
                    "market_name": listing.get("marketPlaceName"),
                    "market_list": listing.get("marketListName"),
                    "company_name": company.get("name"),
                    "identity_verified": raw.get("orderbookId") == book_id
                        and isinstance(raw.get("isin"), str)
                        and len(raw["isin"]) == 12,
                    "actionable": False,
                })
            except Exception as exc:
                info.append({"requested_book_id": book_id, "error": type(exc).__name__,
                             "identity_verified": False, "actionable": False})
    return {"search_diagnostics": out, "stock_information": info,
            "no_orders": True, "complete_market_universe": False}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))
