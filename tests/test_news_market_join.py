from datetime import datetime, timezone, timedelta

from src.news_market_join import enrich_news_with_quotes
from src.swedish_stock_news import NewsItem

NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
INSTRUMENTS = [{"isin": "SE0000115446", "symbol": "VOLV B", "mic": "XSTO"}]
QUOTE = {"SE0000115446": {"last_price": 320.4, "volume": 1076328,
                           "is_real_time": False}}


def item(**changes):
    fields = dict(source="fixture", url="https://example.org/issuer", headline="Quarterly report",
                  published_at=NOW - timedelta(hours=1), isin="SE0000115446",
                  symbol="VOLV B", verified_instrument=True)
    fields.update(changes)
    return NewsItem(**fields)


def test_join_requires_verified_identity_and_remains_nonactionable():
    result = enrich_news_with_quotes([item()], INSTRUMENTS, QUOTE, now=NOW)
    assert len(result["matched"]) == 1
    assert result["matched"][0]["last_price"] == 320.4
    assert result["matched"][0]["actionable"] is False
    assert result["actionable_count"] == 0


def test_unverified_publisher_headline_cannot_match():
    result = enrich_news_with_quotes([item(verified_instrument=False)], INSTRUMENTS, QUOTE, now=NOW)
    assert not result["matched"] and result["unverified_news"] == 1


def test_missing_quote_is_not_invented():
    result = enrich_news_with_quotes([item()], INSTRUMENTS, {}, now=NOW)
    assert not result["matched"] and result["missing_quotes"] == 1


def test_invalid_price_rejected():
    result = enrich_news_with_quotes([item()], INSTRUMENTS,
                                     {"SE0000115446": {"last_price": float("nan"), "volume": 3}},
                                     now=NOW)
    assert not result["matched"] and result["invalid_quotes"] == 1


def test_wrong_share_class_rejected():
    result = enrich_news_with_quotes([item(symbol="VOLV A")], INSTRUMENTS, QUOTE, now=NOW)
    assert not result["matched"] and result["unverified_news"] == 1
