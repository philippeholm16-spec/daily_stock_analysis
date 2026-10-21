from datetime import datetime, timedelta, timezone

from src.news_first_discovery import classify_catalyst
from src.news_headline_watchlist import build_headline_watchlist
from src.swedish_stock_news import NewsItem


NOW = datetime(2026, 10, 21, 13, tzinfo=timezone.utc)


def news(headline, url="https://example.org/a", hours=1):
    return NewsItem(source="fixture", url=url, headline=headline,
                    published_at=NOW - timedelta(hours=hours), isin=None, symbol=None)


def test_live_headline_patterns():
    assert "financing" in classify_catalyst("Två flaggor i Incoax emission")
    assert "financing" in classify_catalyst("Bolaget tar in kapital")
    assert "report" in classify_catalyst("Bulten ökar rörelseresultatet kraftigt i tredje kvartalet")


def test_watchlist_prioritizes_without_inventing_identity():
    result = build_headline_watchlist([news("Bolaget tar in kapital")], now=NOW)
    assert len(result) == 1
    assert result[0]["instrument_status"] == "UNVERIFIED"
    assert result[0]["actionable"] is False


def test_watchlist_deduplicates_and_excludes_stale():
    items = [news("Bolaget tar in kapital"), news("Bolaget tar in kapital"),
             news("Bolaget rapport", url="https://example.org/old", hours=50)]
    assert len(build_headline_watchlist(items, now=NOW)) == 1


def test_watchlist_skips_uncategorized():
    assert build_headline_watchlist([news("Kommentar om marknaden")], now=NOW) == []
