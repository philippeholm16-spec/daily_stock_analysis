"""Tests for the news-source inventory and access gating."""
from src.swedish_news_sources import SOURCES, enabled_sources, source_summary


def test_broad_inventory():
    assert len(SOURCES) >= 15
    assert {"Dagens industri", "Placera", "MFN", "Finwire", "Nasdaq Nordic"}.issubset(
        {s.name for s in SOURCES})


def test_no_unapproved_fetch():
    assert not enabled_sources()
    assert source_summary()["enabled"] == 0


def test_no_unverified_feed_urls():
    assert all(s.feed_url is None or s.feed_url.startswith("https://") for s in SOURCES)


def test_unique_publishers():
    assert len({s.name for s in SOURCES}) == len(SOURCES)
