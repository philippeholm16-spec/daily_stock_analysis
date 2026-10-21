from datetime import datetime, timezone
from src.news_first_discovery import parse_news_feed, discover_news_candidates, classify_catalyst

RSS = b"""<rss><channel><item><title>Bolaget publicerar kvartalsrapport</title>
<link>https://example.org/news/1</link><pubDate>Wed, 21 Oct 2026 08:00:00 GMT</pubDate>
<isin>SE0000115446</isin></item></channel></rss>"""
STOCKS = [{"isin": "SE0000115446", "symbol": "VOLV B", "mic": "XSTO"}]
NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)


def test_verified_explicit_isin_links_news():
    result = discover_news_candidates(RSS, source="fixture", instruments=STOCKS,
                                      now=NOW, verified_isin_field=True)
    assert result["parsed"] == 1 and len(result["candidates"]) == 1
    assert result["candidates"][0]["catalysts"] == ("report",)
    assert result["candidates"][0]["actionable"] is False


def test_untrusted_isin_does_not_link():
    result = discover_news_candidates(RSS, source="fixture", instruments=STOCKS, now=NOW)
    assert not result["candidates"] and result["unlinked"] == 1


def test_wrong_isin_not_linked():
    data = RSS.replace(b"SE0000115446", b"SE0000115447")
    result = discover_news_candidates(data, source="fixture", instruments=STOCKS,
                                      now=NOW, verified_isin_field=True)
    assert not result["candidates"]


def test_atom_link_and_timestamp():
    atom = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
    <title>Major order announced</title><link href="https://example.org/2"/>
    <updated>2026-10-21T08:00:00Z</updated><isin>SE0000115446</isin>
    </entry></feed>"""
    news, errors = parse_news_feed(atom, source="fixture", verified_isin_field=True)
    assert not errors and news[0].url == "https://example.org/2"
    assert classify_catalyst(news[0].headline) == ("order",)


def test_no_timestamp_rejected():
    news, errors = parse_news_feed(b"<rss><item><title>x</title></item></rss>", source="fixture")
    assert not news and errors == ["invalid_feed_entry"]
