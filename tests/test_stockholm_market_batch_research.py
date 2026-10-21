"""Whole-market batches use real mapped identities, never publisher guesses."""
import asyncio
from datetime import datetime, timedelta, timezone
from src.stockholm_universe_batch import BatchPlan
from scripts.stockholm_market_batch_research import scan_batch


NOW = datetime(2026, 10, 21, 14, tzinfo=timezone.utc)
STOCK = {"isin": "SE0000115446", "symbol": "VOLV B", "segment": "Large Cap",
         "order_book_id": "5269", "mic": "XSTO", "currency": "SEK"}
OTHER = {"isin": "SE0021628898", "symbol": "VOLCAR B", "segment": "Large Cap",
         "order_book_id": "1296604", "mic": "XSTO", "currency": "SEK"}
PLAN = BatchPlan("synthetic_verified_hash", True, 0, 2, 2, 4,
                 (STOCK, OTHER))


def chart():
    candle = []
    for i in range(40):
        close = 100 + i*0.05
        candle.append({
            "timestamp": int((NOW - timedelta(minutes=10*(39-i))).timestamp()*1000),
            "open": close-0.03, "high": 110 if i in (28,30) else close+0.04,
            "low": close-0.15, "close": close,
            "totalVolumeTraded": 5000 if i == 39 else 1500,
        })
    return {"data": {"ohlc": candle,
                     "metadata": {"resolution": {"chartResolution": "ten_minutes"}}},
            "pagination": {"offset": 0, "returned": 40, "total": 40}}


def test_scanner_analyzes_valid_stock_and_rejects_wrong_isin():
    calls = []
    async def fake_provider(name, args):
        calls.append((name, args["order_book_id"]))
        book = args["order_book_id"]
        if name == "get_stock_info":
            return {
                "orderbookId": book,
                "isin": STOCK["isin"] if book == "5269" else "SE0000000000",
                "name": "Volvo B" if book == "5269" else "Wrong security",
                "listing": {
                    "tickerSymbol": STOCK["symbol"] if book == "5269" else OTHER["symbol"],
                    "currency": "SEK", "marketPlaceCode": "XSTO",
                },
            }
        if name == "get_stock_quote":
            return {"last": 101.95, "totalVolumeTraded": 65000.0,
                    "totalValueTraded": 10_000_000, "buy": 101.90,
                    "sell": 102.0, "isRealTime": False}
        if name == "get_stock_chart":
            return chart()
        raise AssertionError("unexpected_call")
    async def immediate(_): pass
    result = asyncio.run(scan_batch(
        PLAN, fake_provider, now=NOW, sleep=immediate
    ))
    assert result["provider_requests"] == 4
    assert result["stocks_reviewed_or_explicitly_unavailable"] == 1
    assert result["stocks_rejected"] == 1
    assert result["results"][0]["stock_analyst"]["score"] is not None
    assert result["results"][0]["actionable"] is False
    assert result["results"][1]["status"] == "REJECTED"
    assert result["entire_stockholm_price_scan_completed"] is False
    assert result["actionable_count"] == 0


def test_scanner_is_bounded_and_does_not_trust_missing_charts():
    async def fake_provider(name, args):
        if name == "get_stock_info":
            return {
                "orderbookId": "5269", "isin": STOCK["isin"], "name": "Volvo B",
                "listing": {"tickerSymbol": STOCK["symbol"], "currency": "SEK",
                            "marketPlaceCode": "XSTO"}
            }
        if name == "get_stock_quote":
            return {"last": 101.95, "totalVolumeTraded": 1000,
                    "isRealTime": False}
        if name == "get_stock_chart":
            raise TimeoutError("provider returned no chart")
    plan = BatchPlan("sample", True, 0, 1, 1, 1, (STOCK,))
    async def immediate(_): pass
    result = asyncio.run(scan_batch(plan, fake_provider, now=NOW, sleep=immediate))
    assert result["stocks_rejected"] == 1
    assert result["very_good_indicative_setups"] == 0
    assert all(row["actionable"] is False for row in result["results"])
