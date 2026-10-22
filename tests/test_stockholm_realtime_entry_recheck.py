"""Reprice only independently validated primary XSTO quotes, not delayed prices."""
from datetime import datetime, timedelta, timezone

from src.stockholm_realtime_quality import evaluate_primary_live_quote
from src.stockholm_realtime_entry_recheck import reprice_with_live_quote


NOW = datetime(2026, 10, 22, 7, 30, tzinfo=timezone.utc)
ISIN = "SE0000115446"
SYM = "VOLV B"
CONID = 23456


def verified_quote(*, type_id=1, ask=100.05):
    snapshot = {
        "provider": "IBKR_TWS_API", "market_data_type": type_id,
        "entitlement_confirmed": True, "rights_confirmed": True,
        "session_authenticated": True,
        "contract_id": CONID, "isin": ISIN, "symbol": SYM,
        "listing_mic": "XSTO", "currency": "SEK",
        "trade_venue_mic": "XSTO", "book_venue_mic": "XSTO",
        "exchange_mapping_confirmed": True, "market_phase": "CONTINUOUS",
        "trade_ts_utc": (NOW-timedelta(seconds=3)).isoformat(),
        "bid_ask_ts_utc": (NOW-timedelta(seconds=2)).isoformat(),
        "received_at_utc": (NOW-timedelta(seconds=1)).isoformat(),
        "last": 100, "bid": ask-0.15, "ask": ask,
    }
    instrument = {"contract_id": CONID, "isin": ISIN,
                  "symbol": SYM, "listing_mic": "XSTO"}
    return evaluate_primary_live_quote(snapshot, instrument, now=NOW)


def research(*, chart_minutes=5):
    return {
        "status": "ANALYZED_INDICATIVE_SETUP",
        "opportunity_grade": "VERY_GOOD", "score": 90,
        "entry_price": 100, "lowest_sell_point": 98, "sell_point": 106,
        "chart_as_of": (NOW-timedelta(minutes=chart_minutes)).isoformat(),
        "source_news_opinion_used": False, "actionable": False,
    }


def test_live_quote_can_be_repriced_at_actual_ask_for_human_review():
    gate = verified_quote()
    assert gate.accepted_as_primary_live
    result = reprice_with_live_quote(
        research(), gate, isin=ISIN, symbol=SYM, now=NOW
    )
    assert result["status"] == "LIVE_QUOTE_REPRICED_FOR_HUMAN_RESEARCH"
    assert result["levels"]["entry_ask"] == 100.05
    assert result["levels"]["target"] == 106
    assert result["levels"]["stop_loss"] == 98
    assert result["levels"]["net_rr"] >= 2
    assert result["levels"]["risk_sek"] <= 150
    assert result["actionable"] is False
    assert result["trade_signal"] is None


def test_unsubscribed_delayed_quote_never_reprices():
    gate = verified_quote(type_id=3)
    assert not gate.accepted_as_primary_live
    result = reprice_with_live_quote(
        research(), gate, isin=ISIN, symbol=SYM, now=NOW
    )
    assert result["status"] == "LIVE_SETUP_REJECTED"


def test_quote_gap_breaks_historical_plan():
    gate = verified_quote(ask=103)
    assert gate.accepted_as_primary_live
    result = reprice_with_live_quote(
        research(), gate, isin=ISIN, symbol=SYM, now=NOW
    )
    assert result["status"] == "LIVE_SETUP_REJECTED"
    assert "live_entry_invalidated_historical_levels" in result["reasons"]


def test_stale_candles_cannot_be_upgraded_by_live_last():
    gate = verified_quote()
    result = reprice_with_live_quote(
        research(chart_minutes=65), gate, isin=ISIN, symbol=SYM, now=NOW
    )
    assert result["status"] == "LIVE_SETUP_REJECTED"
    assert "reference_bars_or_live_quote_stale" in result["reasons"]


def test_wrong_isin_no_live_approval():
    gate = verified_quote()
    result = reprice_with_live_quote(
        research(), gate, isin="SE0021628898", symbol=SYM, now=NOW
    )
    assert result["status"] == "LIVE_SETUP_REJECTED"


def test_unapproved_stock_analyst_grade_cannot_be_repriced():
    gate = verified_quote()
    data = research()
    data["opportunity_grade"] = "WATCH_ONLY"
    result = reprice_with_live_quote(
        data, gate, isin=ISIN, symbol=SYM, now=NOW
    )
    assert result["status"] == "LIVE_SETUP_REJECTED"
