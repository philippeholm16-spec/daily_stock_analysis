from datetime import datetime, timezone, timedelta

from src.swedish_stock_news import NewsItem, link_news


def item(**kwargs):
    base = dict(source="Issuer", url="https://example.org/release", headline="Quarterly report",
                published_at=datetime.now(timezone.utc) - timedelta(hours=1),
                isin="SE0000115446", symbol="VOLV B", verified_instrument=True)
    base.update(kwargs)
    return NewsItem(**base)


def test_verified_isin_links():
    linked, rejected = link_news([item()], [{"isin": "SE0000115446", "symbol": "VOLV B", "mic": "XSTO"}])
    assert len(linked) == 1 and not rejected


def test_headline_or_ticker_alone_cannot_link():
    linked, rejected = link_news([item(isin=None)], [{"isin": "SE0000115446", "symbol": "VOLV B", "mic": "XSTO"}])
    assert not linked and rejected[0][1] == "instrument_not_verified_by_isin"


def test_stale_news_rejected():
    linked, rejected = link_news([item(published_at=datetime.now(timezone.utc) - timedelta(days=5))],
                                 [{"isin": "SE0000115446", "symbol": "VOLV B", "mic": "XSTO"}])
    assert not linked and rejected[0][1] == "invalid_or_stale_publication_time"


def test_wrong_share_class_rejected():
    linked, rejected = link_news([item(symbol="VOLV A")],
                                 [{"isin": "SE0000115446", "symbol": "VOLV B", "mic": "XSTO"}])
    assert not linked and rejected[0][1] == "ticker_mismatch"
