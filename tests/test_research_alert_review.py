"""Review all potential Telegram research alerts before sending."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest

from src.research_alert_review import review_research_report


NOW = datetime(2026, 10, 21, 16, tzinfo=timezone.utc)


def fixture():
    return {
        "fetched_at_utc": NOW.isoformat(),
        "capital_sek": 15000,
        "trade_signals_enabled": False,
        "actionable_count": 0,
        "research_candidates": [{
            "isin": "SE0003849223", "ticker": "BULTEN", "mic": "XSTO",
            "headline": "Bulten ökar rörelseresultatet i tredje kvartalet",
            "source": "Placera",
            "published_at": (NOW-timedelta(hours=1)).isoformat(),
            "news_url": "https://www.placera.se/nyheter/bulten-test",
            "discovery_priority": 6, "actionable": False, "trade_signal": None,
            "publisher_isin_confirmed": False, "timestamp_verified": False,
            "stock_analyst": {
                "engine": "Stock Analyst Sweden / independent technical v1",
                "status": "ANALYZED_NO_VALID_SETUP",
                "score": 65, "quality": "Måttlig teknisk styrka",
                "why": ["Stigande trend"], "risks": ["Motstånd saknas"],
                "lowest_sell_point": None, "sell_point": None,
                "potential_pct": None, "entry_price": None,
                "actionable": False, "data_verified_real_time": False,
                "source_news_opinion_used": False,
            },
        }],
    }


def test_safe_report_reviews_every_candidate():
    doc = fixture()
    result = review_research_report(doc, now=NOW)
    assert result["checked"] == 1 and result["all_checked"]
    assert len(result["accepted"]) == 1 and result["actionable_count"] == 0


def test_trading_claim_blocks_entire_report():
    doc = fixture()
    doc["trade_signals_enabled"] = True
    with pytest.raises(ValueError, match="report_attempts_trading"):
        review_research_report(doc, now=NOW)


def test_row_with_fake_trade_signal_rejected():
    doc = fixture()
    doc["research_candidates"][0]["trade_signal"] = {"buy": 12}
    result = review_research_report(doc, now=NOW)
    assert len(result["rejected"]) == 1
    assert "trading_claim" in result["rejected"][0]["reasons"]


def test_old_report_cannot_trigger_alerts():
    doc = fixture()
    doc["fetched_at_utc"] = (NOW-timedelta(hours=2)).isoformat()
    with pytest.raises(ValueError, match="stale"):
        review_research_report(doc, now=NOW)


def test_editorial_article_from_unapproved_domain_rejected():
    doc = fixture()
    doc["research_candidates"][0]["news_url"] = "https://unknown.example/trade"
    result = review_research_report(doc, now=NOW)
    assert "unapproved_article_source" in result["rejected"][0]["reasons"]


def test_duplicates_and_old_articles_rejected():
    doc = fixture()
    duplicate = deepcopy(doc["research_candidates"][0])
    old = deepcopy(duplicate)
    old["published_at"] = (NOW-timedelta(days=2)).isoformat()
    old["news_url"] = "https://www.placera.se/nyheter/old"
    doc["research_candidates"].extend([duplicate, old])
    result = review_research_report(doc, now=NOW)
    assert result["checked"] == 3 and result["all_checked"]
    assert len(result["accepted"]) == 1 and len(result["rejected"]) == 2

def test_missing_stock_analyst_never_passes_review():
    doc = fixture()
    doc["research_candidates"][0].pop("stock_analyst")
    result = review_research_report(doc, now=NOW)
    assert not result["accepted"]
    assert "stock_analyst_analysis_missing" in result["rejected"][0]["reasons"]


def test_publisher_opinion_used_blocks_research():
    doc = fixture()
    doc["research_candidates"][0]["stock_analyst"]["source_news_opinion_used"] = True
    result = review_research_report(doc, now=NOW)
    assert not result["accepted"]
    assert "unverified_or_publisher_influenced_analysis" in result["rejected"][0]["reasons"]


def test_unsupported_levels_rejected():
    doc = fixture()
    doc["research_candidates"][0]["stock_analyst"]["sell_point"] = 200
    result = review_research_report(doc, now=NOW)
    assert not result["accepted"]
    assert "invented_levels_on_unapproved_analysis" in result["rejected"][0]["reasons"]
