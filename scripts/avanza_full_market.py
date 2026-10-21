"""Read-only whole-universe Avanza MCP quote collection, opt-in.

Requires an independently verified complete Nasdaq Stockholm universe manifest
with exact Avanza order-book IDs. No broad search discovery, no credentials,
no trading signals, no automatic scheduling. Partial data is explicitly reported.
"""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from src.avanza_mcp_adapter import parse_public_quote
from scripts.avanza_mcp_bridge import unwrap, normalize_quote


def load_manifest(path):
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("manifest_must_be_object")
    if document.get("complete_main_market") is not True:
        raise ValueError("complete_market_coverage_not_asserted")
    if not document.get("source") or not document.get("source_verified"):
        raise ValueError("unverified_universe_source")
    stamp = datetime.fromisoformat(document["as_of"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    if stamp.tzinfo is None or not 0 <= (now - stamp).total_seconds() <= 86400:
        raise ValueError("missing_or_stale_universe_timestamp")
    rows = document.get("listings")
    if not isinstance(rows, list) or not rows:
        raise ValueError("missing_universe_listings")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid_listing")
        if (row.get("segment") not in ("Large Cap", "Mid Cap", "Small Cap")
                or row.get("mic") != "XSTO" or row.get("currency") != "SEK"
                or row.get("instrument_type") != "EQUITY"
                or row.get("active") is not True):
            raise ValueError("unsupported_listing")
        if (not isinstance(row.get("isin"), str) or len(row["isin"]) != 12
                or not isinstance(row.get("symbol"), str) or not row["symbol"].strip()
                or not isinstance(row.get("order_book_id"), str)
                or not row["order_book_id"].isascii()
                or not row["order_book_id"].isdecimal()):
            raise ValueError("invalid_listing_identity_or_avanza_id")
        key = (row["isin"], row["symbol"])
        if key in seen:
            raise ValueError("duplicate_listing")
        seen.add(key)
    # A user-provided assertion is not independent evidence of full coverage.
    return document, rows


async def collect(rows, delay_seconds):
    from fastmcp import Client
    from avanza_mcp import mcp
    result = []
    async with Client(mcp) as client:
        for row in rows:
            entry = {k: row[k] for k in ("isin", "symbol", "order_book_id")}
            try:
                # Confirm ISIN and currency using a separate identity endpoint.
                info = unwrap(await client.call_tool("get_stock_info", {
                    "order_book_id": row["order_book_id"]
                }))
                listing = info.get("listing") or {}
                if (info.get("isin") != row["isin"]
                        or listing.get("currency") != row["currency"]
                        or str(info.get("orderbookId")) != row["order_book_id"]):
                    raise ValueError("instrument_identity_mismatch")
                quote_raw = unwrap(await client.call_tool("get_stock_quote", {
                    "order_book_id": row["order_book_id"]
                }))
                quote = parse_public_quote(normalize_quote(quote_raw),
                                           order_book_id=row["order_book_id"])
                entry.update(price=quote.price, volume=quote.volume,
                             is_real_time_reported=quote_raw.get("isRealTime"),
                             provider_updated_raw=quote_raw.get("updated"),
                             provider_time_of_last_raw=quote_raw.get("timeOfLast"),
                             status="DATA_ONLY_TIMESTAMP_UNVERIFIED",
                             actionable=False)
            except Exception as exc:
                entry.update(status="REJECTED", actionable=False,
                             error=type(exc).__name__)
            result.append(entry)
            if delay_seconds:
                await asyncio.sleep(delay_seconds)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("avanza_universe_diagnostic.json"))
    p.add_argument("--delay-seconds", type=float, default=2.0)
    args = p.parse_args()
    if not 1 <= args.delay_seconds <= 60:
        p.error("delay-seconds must be between 1 and 60 to avoid rapid polling")
    doc, rows = load_manifest(args.manifest)
    print(f"Requesting public Avanza quotes for {len(rows)} manifest entries (read-only)")
    results = asyncio.run(collect(rows, args.delay_seconds))
    accepted = sum(r["status"] == "DATA_ONLY_TIMESTAMP_UNVERIFIED" for r in results)
    report = {
        "source": "unofficial-avanza-mcp",
        "universe_source": doc["source"],
        "universe_complete_independently_verified": False,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "requested": len(rows),
        "data_only": accepted,
        "rejected": len(rows) - accepted,
        "actionable": 0,
        "quotes": results,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"Received {accepted}/{len(rows)} diagnostic quotes; "
          "0 actionable (timestamps and coverage unverified)")


if __name__ == "__main__":
    main()
