"""Contract: EVERY identified candidate is analyzed even when a chart fails."""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from types import ModuleType, SimpleNamespace

from scripts import auto_news_research_probe as probe


def fixture_chart(now):
    bars = []
    for idx in range(40):
        c = 70.0 + 0.1 * idx
        bars.append({"timestamp": int((now-timedelta(minutes=(39-idx)*10)).timestamp()*1000),
                     "open": c, "close": c, "high": c+0.2, "low": c-0.2,
                     "totalVolumeTraded": 1000})
    return {"data": {"ohlc": bars, "metadata": {"resolution": {
                "chartResolution": "ten_minutes"}}},
            "pagination": {"total": 40, "returned": 40, "offset": 0}}


def test_analyze_every_candidate_even_if_one_chart_fails(monkeypatch):
    now = datetime.now(timezone.utc)
    pubdate = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    xml = ('<rss><channel>' + ''.join(
        f'<item><title>{ticker} publicerar kvartalsrapport</title>'
        f'<link>https://www.placera.se/nyheter/{ticker}</link>'
        f'<pubDate>{pubdate}</pubDate></item>'
        for ticker in ["Bulten", "Mips"]) + '</channel></rss>').encode()
    monkeypatch.setattr(probe, "fetch_public_feed", lambda _: xml)

    async def no_delay(_):
        return None

    monkeypatch.setattr(probe.asyncio, "sleep", no_delay)
    identity = {
        "Bulten": ("290011", "SE0003849223", "BULTEN"),
        "Mips": ("506390", "SE0009216278", "MIPS"),
    }

    class FakeClient:
        def __init__(self, _):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            return False
        async def call_tool(self, name, args):
            if name == "search_instruments":
                book, isin, symbol = identity[args["query"]]
                result = {"hits": [{"order_book_id": book, "exchange": "Stockholmsbörsen",
                                    "name": args["query"]}], "totalNumberOfHits": 1}
            elif name == "get_stock_info":
                book = args["order_book_id"]
                company, (book_id, isin, symbol) = next(
                    (k, val) for k, val in identity.items() if val[0] == book)
                result = {"orderbookId": book, "isin": isin, "name": company,
                          "listing": {"marketPlaceCode": "XSTO",
                                      "currency": "SEK", "tickerSymbol": symbol}}
            elif name == "get_stock_quote":
                result = {"last": 73.9 if args["order_book_id"] == "290011" else 50,
                          "buy": 73.8, "sell": 73.9,
                          "totalVolumeTraded": 40000, "isRealTime": False}
            elif name == "get_stock_chart":
                if args["order_book_id"] == "506390":
                    raise TimeoutError("provider unavailable")
                result = fixture_chart(now)
            else:
                raise AssertionError(name)
            return SimpleNamespace(is_error=False, structured_content=result)

    fastmcp = ModuleType("fastmcp")
    fastmcp.Client = FakeClient
    avanza = ModuleType("avanza_mcp")
    avanza.mcp = object()
    monkeypatch.setitem(sys.modules, "fastmcp", fastmcp)
    monkeypatch.setitem(sys.modules, "avanza_mcp", avanza)
    report = asyncio.run(probe.run(max_queries=2, delay_seconds=0.5,
                                   include_google_news=False))
    assert report["metrics"]["matched"] == 2
    assert report["metrics"]["analysis_attempted"] == 2
    assert report["analysis_coverage"]["analyzed_or_explicitly_unavailable"] == 2
    by_ticker = {x["ticker"]: x for x in report["research_candidates"]}
    assert by_ticker["BULTEN"]["stock_analyst"]["score"] is not None
    assert by_ticker["MIPS"]["stock_analyst"]["status"] == "ANALYSIS_UNAVAILABLE"
    assert all(x["stock_analyst"]["source_news_opinion_used"] is False
               for x in report["research_candidates"])
    assert report["actionable_count"] == 0
