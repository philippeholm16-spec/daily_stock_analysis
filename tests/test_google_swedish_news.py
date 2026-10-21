"""Google News public RSS search boundedness and failure behavior."""
from datetime import datetime, timezone

import pytest
from src.google_swedish_news import (build_google_news_queries, collect_google_news,
                                     fetch_google_news)


NOW = datetime(2026, 10, 21, 16, tzinfo=timezone.utc)


def feed(headline="Bulten rapport - Dagens industri"):
    return (f'<rss><channel><item><title>{headline}</title>'
            '<link>https://news.google.com/rss/articles/CBMi123</link>'
            '<pubDate>Wed, 21 Oct 2026 15:00:00 GMT</pubDate>'
            '</item></channel></rss>').encode()


def test_grouped_domain_scoped_queries():
    feeds = build_google_news_queries()
    assert len(feeds) == 3
    assert all(url.startswith("https://news.google.com/rss/search?")
               and "ceid=SE%3Asv" in url and "site%3A" in url
               for url in feeds.values())
    assert any("di.se" in url and "placera.se" in url for url in feeds.values())


def test_news_rss_works_without_keys_and_not_verified():
    result = collect_google_news(now=NOW, fetcher=lambda _: feed())
    assert sum(result["groups"].values()) == 1  # deduplicated across groups
    assert result["news_items"][0].verified_instrument is False
    assert result["actionable"] is False


def test_unavailable_google_feed_degrades_to_errors():
    def fail(_):
        raise TimeoutError("timeout")
    result = collect_google_news(now=NOW, fetcher=fail)
    assert not result["news_items"]
    assert len(result["errors"]) == 3


def test_reject_unlisted_domains():
    with pytest.raises(ValueError, match="unapproved"):
        fetch_google_news("https://evil.example/rss")


def test_ancient_headlines_excluded():
    result = collect_google_news(
        now=datetime(2026, 10, 30, tzinfo=timezone.utc),
        fetcher=lambda _: feed())
    assert not result["news_items"]
