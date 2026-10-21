from datetime import datetime, timedelta, timezone

from src.news_company_research import (
    match_research_headlines, prefix_matches, validate_avanza_identity,
)
from src.swedish_stock_news import NewsItem


NOW = datetime(2026, 10, 21, 14, tzinfo=timezone.utc)


def stock(book="290011", isin="SE0009661986", market="XSTO"):
    return {
        "orderbookId": book,
        "isin": isin,
        "name": "Bulten",
        "listing": {"marketPlaceCode": market,
                    "currency": "SEK", "tickerSymbol": "BULTEN"}
    }


def news(title, *, hours=1, url="https://www.placera.se/nyheter/bulten"):
    return NewsItem(source="Placera", url=url, headline=title,
                    published_at=NOW - timedelta(hours=hours),
                    isin=None, symbol=None, verified_instrument=False)


def test_exact_identity_requires_market_and_isin():
    assert validate_avanza_identity(stock(), expected_book_id="290011")
    assert validate_avanza_identity(stock(market="FNSE"), expected_book_id="290011") is None
    assert validate_avanza_identity(stock(isin=None), expected_book_id="290011") is None
    assert validate_avanza_identity(stock(), expected_book_id="290012") is None


def test_headline_name_is_strict_boundary():
    assert prefix_matches("Bulten ökar rörelseresultatet", "Bulten")
    assert prefix_matches("Byggmax: kan vara värd att hålla ögonen på", "Byggmax")
    assert not prefix_matches("Bultens rapport", "Bulten")
    assert not prefix_matches("Nyheter om Bulten idag", "Bulten")
    assert not prefix_matches("Bultenite föll", "Bulten")


def test_matched_headline_and_quote_always_nonactionable():
    identity = validate_avanza_identity(stock(), expected_book_id="290011")
    data = match_research_headlines(
        [news("Bulten ökar rörelseresultatet")],
        {"290011": identity}, {"290011": "Bulten"},
        {"290011": {"last": 41.5, "totalVolumeTraded": 10299.0,
                    "isRealTime": False}},
        now=NOW
    )
    assert data["coverage"]["matched"] == 1
    row = data["candidates"][0]
    assert row["last_price"] == 41.5 and row["volume"] == 10299
    assert row["publisher_isin_confirmed"] is False
    assert row["actionable"] is False
    assert data["actionable_count"] == 0


def test_no_quote_does_not_become_price():
    identity = validate_avanza_identity(stock(), expected_book_id="290011")
    data = match_research_headlines(
        [news("Bulten rapport")], {"290011": identity},
        {"290011": "Bulten"}, {}, now=NOW
    )
    assert data["coverage"]["quote_unavailable"] == 1
    assert data["candidates"][0]["last_price"] is None


def test_ambiguous_name_rejected():
    identity = validate_avanza_identity(stock(), expected_book_id="290011")
    second = {**identity, "isin": "SE0000115446", "order_book_id": "5269"}
    data = match_research_headlines(
        [news("Bulten rapport")],
        {"290011": identity, "5269": second},
        {"290011": "Bulten", "5269": "Bulten"}, {},
        now=NOW
    )
    assert not data["candidates"]
    assert data["coverage"]["ambiguous"] == 1


def test_stale_news_filtered():
    identity = validate_avanza_identity(stock(), expected_book_id="290011")
    result = match_research_headlines(
        [news("Bulten rapport", hours=49)],
        {"290011": identity}, {"290011": "Bulten"},
        {}, now=NOW
    )
    assert not result["candidates"]
    assert result["coverage"]["stale"] == 1
