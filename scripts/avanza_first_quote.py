"""One-stock public Avanza MCP connectivity smoke test (no account login).

Run: python -m scripts.avanza_first_quote --query 'Volvo B'
Prints raw provider data and status. Does not produce trading signals.
"""
import argparse
import asyncio
import json


def unwrap(result):
    if getattr(result, "is_error", False):
        raise RuntimeError("MCP returned tool error")
    data = getattr(result, "structured_content", None)
    if not isinstance(data, dict):
        raise ValueError("No structured MCP response")
    return data.get("result", data)


async def check(query, order_book_id=None):
    from fastmcp import Client
    from avanza_mcp import mcp
    async with Client(mcp) as client:
        found = unwrap(await client.call_tool("search_instruments", {
            "query": query, "instrument_type": "stock", "limit": 20
        }))
        hits = found.get("hits", [])
        print("SEARCH:", json.dumps(hits, ensure_ascii=False, indent=2))
        if not hits:
            raise ValueError("No stock candidates returned")
        # Never silently select a similarly named share class.
        for hit in hits:
            print("CANDIDATE:", hit.get("name"), hit.get("isin"),
                  hit.get("exchange"), hit.get("order_book_id"))
        ids = [h.get("order_book_id") for h in hits
               if h.get("order_book_id") and h.get("isin")
               and h.get("currency") == "SEK"]
        if order_book_id is not None:\n            if order_book_id not in [h.get("order_book_id") for h in hits]:\n                raise ValueError("Selected Avanza ID not present in search results")\n            ids = [order_book_id]\n        if len(ids) != 1:
            print("AMBIGUOUS: Select an exact verified order-book ID from the candidates.")
            return
        quote = unwrap(await client.call_tool("get_stock_quote", {
            "order_book_id": ids[0]
        }))
        print("QUOTE:", json.dumps(quote, ensure_ascii=False, indent=2))
        print("DATA_ONLY: No freshness or identity verification for trading.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="Volvo B")
    parser.add_argument("--order-book-id", default=None)\n    args = parser.parse_args()
    asyncio.run(check(args.query, args.order_book_id))


if __name__ == "__main__":
    main()
