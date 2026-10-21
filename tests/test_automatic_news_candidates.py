from datetime import datetime, timezone, timedelta

from src.automatic_news_candidates import (
    extract_issuer_query, select_headline_searches, assess_search_candidates,
    rank_research_candidate,
)
from src.swedish_stock_news import NewsItem


NOW = datetime(2026, 10, 21, 14, tzinfo=timezone.utc)


def story(title, *, age=1, url="https://www.placera.se/nyheter/test"):
    return NewsItem(source="Placera", url=url, headline=title,
                    published_at=NOW - timedelta(hours=age),
                    isin=None, symbol=None)


def info(book_id, name, isin, market="XSTO"):
    return {"orderbookId": book_id, "name": name, "isin": isin,
            "listing": {"marketPlaceCode": market,
                        "currency": "SEK", "tickerSymbol": "BULTEN"}}


def test_title_extraction_and_editorial_rejection():
    assert extract_issuer_query("Bulten ökar rörelseresultatet") == "Bulten"
    assert extract_issuer_query("Inhalation Sciences tar in kapital") == "Inhalation Sciences"
    assert extract_issuer_query("SKF:s rapport förbättras") == "SKF"
    assert extract_issuer_query("Två flaggor i Incoax emission") is None
    assert extract_issuer_query("Negativa rapportrörelser på börsen") is None


def test_headline_search_is_bounded_and_requires_catalyst():
    news = [story("Bulten ökar rörelseresultatet"),
            story("Inhalation Sciences tar in kapital"),
            story("Byggmax: kan vara intressant"),
            story("SKF:s rapport förbättras")]
    queries, rejected = select_headline_searches(news, now=NOW, max_queries=2)
    assert [q["query"] for q in queries] == ["Bulten", "Inhalation Sciences"]
    assert any(x["reason"] == "query_budget_exceeded" for x in rejected)


def test_verified_single_match():
    row = {"query": "Bulten", "headline": "Bulten ökar rörelseresultatet"}
    hits = [{"order_book_id": "290011", "exchange": "Stockholmsbörsen"}]
    identity, reason = assess_search_candidates(
        row, hits, {"290011": info("290011", "Bulten", "SE0003849223")})
    assert reason is None and identity["isin"] == "SE0003849223"


def test_reject_multiple_share_classes():
    row = {"query": "Volvo", "headline": "Volvo rapporterar resultat"}
    hits = [{"order_book_id": "1", "exchange": "Stockholmsbörsen"},
            {"order_book_id": "2", "exchange": "Stockholmsbörsen"}]
    infos = {"1": info("1", "Volvo A", "SE0000000001"),
             "2": info("2", "Volvo B", "SE0000000002")}
    identity, reason = assess_search_candidates(row, hits, infos)
    assert identity is None and reason == "ambiguous_share_class"


def test_first_north_rejected():
    row = {"query": "Inhalation Sciences", "headline": "Inhalation Sciences tar in kapital"}
    hit = [{"order_book_id": "123", "exchange": "First North Stockholm"}]
    identity, reason = assess_search_candidates(
        row, hit, {"123": info("123", "Inhalation Sciences", "SE0000000003", "FNSE")})
    assert identity is None and reason == "no_verified_xsto_identity"


def test_score_research_only_delayed_quotes():
    row = {"query": "Bulten", "headline": "Bulten ökar rörelseresultatet",
           "catalysts": ("report",), "published_at": (NOW - timedelta(hours=1)).isoformat(),
           "url": "https://www.placera.se/news", "source": "Placera"}
    stock = {"isin": "SE0003849223", "order_book_id": "290011", "ticker": "BULTEN",
             "stock_name": "Bulten", "mic": "XSTO"}
    result = rank_research_candidate(row, stock,
                                     {"last": 75.8, "totalVolumeTraded": 373794.0,
                                      "buy": 75.7, "sell": 75.8, "isRealTime": False},
                                     fetched_at=NOW)
    assert result["discovery_priority"] == 7
    assert result["turnover_proxy_sek"] > 5_000_000
    assert result["spread_pct"] is not None
    assert result["relative_volume"] is None
    assert result["actionable"] is False and result["trade_signal"] is None


def test_missing_quote_does_not_invent_trade():
    row = {"catalysts": ("guidance",), "published_at": NOW.isoformat(),
           "headline": "Test", "url": "https://example.org", "source": "Fixture"}
    result = rank_research_candidate(row, {"isin": "SE0000000001"}, {}, fetched_at=NOW)
    assert result["last_price"] is None
    assert not result["actionable"]
