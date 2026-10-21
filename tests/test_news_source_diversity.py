"""Balanced bounded discovery tests; never claim these are trade signals."""
from datetime import datetime, timedelta, timezone

from src.news_source_diversity import select_diverse_searches
from src.swedish_stock_news import NewsItem


NOW = datetime(2026, 10, 21, 15, tzinfo=timezone.utc)


def row(company, source):
    return NewsItem(source=source,
                    headline=company + " publicerar kvartalsrapport",
                    url="https://news.google.com/rss/articles/" + company
                        if source.startswith("Google") else
                        "https://www.placera.se/nyheter/" + company,
                    published_at=NOW-timedelta(hours=1), isin=None, symbol=None)


def test_quota_balances_sources_without_ticker_duplicates():
    direct = [row(x, "Placera") for x in
              ("Bulten", "Mips", "Byggmax", "Lagercrantz", "SKF", "Securitas")]
    indexed = (
        [row(x, "Google News:financial_press") for x in
         ("Hexpol", "Volvo", "Boliden", "Bulten")] +
        [row(x, "Google News:analysis") for x in
         ("Hexatronic", "Castellum", "Hemnet")] +
        [row(x, "Google News:company_releases") for x in
         ("Assa", "Sobi", "Betsson")]
    )
    selected, reasons, counts = select_diverse_searches(
        direct, indexed, now=NOW, max_queries=10)
    assert len(selected) == 10
    assert counts == {"publisher": 4, "financial_press": 2,
                      "analysis": 2, "company_releases": 2}
    queries = [x["query"] for x in selected]
    assert len(queries) == len(set(queries))


def test_empty_sources_do_not_consume_others_quota():
    direct = [row(x, "Placera") for x in
              ("Bulten", "Mips", "Byggmax", "Lagercrantz", "Securitas")]
    selected, reasons, counts = select_diverse_searches(direct, [], now=NOW)
    assert len(selected) == 5
    assert counts["publisher"] == 5
