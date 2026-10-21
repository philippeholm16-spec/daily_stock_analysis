"""Opt-in Avanza MCP -> Swedish trading bot diagnostic bridge.

Runs only when explicitly invoked. No authentication, orders, trading signals,
Telegram, or full-market claims. Requires Python >=3.12 and avanza-mcp.
"""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from src.avanza_mcp_adapter import parse_public_quote, AvanzaDataError


def unwrap(result):
    if getattr(result, "is_error", False):
        raise RuntimeError("Avanza MCP returned an error")
    data = getattr(result, "structured_content", None)
    if not isinstance(data, dict):
        raise ValueError("Missing structured MCP result")
    # FastMCP may wrap structured output in {'result': ...}.
    if isinstance(data.get("result"), dict):
        return data["result"]
    return data


def normalize_quote(raw):
    """Avanza Quote fields, as defined in upstream models/stock.py."""
    if not isinstance(raw, dict):
        raise AvanzaDataError("invalid_raw_quote")
    last = raw.get("last")
    volume = raw.get("totalVolumeTraded")
    # Upstream timestamp fields are integer-valued and may use undocumented
    # units; never infer timestamp units or freshness from receipt time.
    return {"last_price": last, "volume": volume}


async def fetch(order_book_ids):
    # Import only when running this opt-in command.
    from fastmcp import Client
    from avanza_mcp import mcp
    results = []
    async with Client(mcp) as client:
        for order_book_id in order_book_ids:
            try:
                raw = unwrap(await client.call_tool(
                    "get_stock_quote", {"order_book_id": order_book_id}
                ))
                quote = parse_public_quote(normalize_quote(raw),
                                           order_book_id=order_book_id)
                results.append({
                    "order_book_id": quote.order_book_id,
                    "last_price": quote.price,
                    "volume": quote.volume,
                    "provider_is_real_time": raw.get("isRealTime"),
                    "provider_updated_raw": raw.get("updated"),
                    "provider_time_of_last_raw": raw.get("timeOfLast"),
                    "as_of": None,
                    "timestamp_verified": False,
                    "actionable": False,
                    "status": "DATA_ONLY_TIMESTAMP_UNVERIFIED",
                })
            except Exception as exc:
                results.append({"order_book_id": order_book_id, "actionable": False,
                                "status": "REJECTED", "error": type(exc).__name__})
    return results


def main():
    parser = argparse.ArgumentParser(description="Avanza MCP data-only diagnostic")
    parser.add_argument("--order-book-id", action="append", required=True,
                        help="Verified Avanza order-book ID; repeat for multiple")
    parser.add_argument("--output", type=Path,
                        default=Path("avanza_diagnostic.json"))
    args = parser.parse_args()
    if any(not value.isdigit() for value in args.order_book_id):
        parser.error("order-book-id must contain only digits")
    result = {
        "source": "unofficial-avanza-mcp",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "for_diagnostics_only": True,
        "coverage": "selected order-book IDs only, not Nasdaq Stockholm universe",
        "quotes": asyncio.run(fetch(args.order_book_id)),
    }
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
