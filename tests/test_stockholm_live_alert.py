"""No Stock Analyst Telegram alert without validated primary live quote and RR."""
from datetime import datetime, timedelta, timezone
from copy import deepcopy

from src.stockholm_realtime_quality import evaluate_primary_live_quote
from src.stockholm_live_alert import build_live_alert


NOW = datetime(2026, 10, 22, 7, 30, 0, tzinfo=timezone.utc)
INSTRUMENT = {"isin": "SE0000115446", "symbol": "VOLV B", "mic": "XSTO",
              "listing_mic": "XSTO",
              "contract_id": 1234567}


def raw_quote(*, market_type=1, ask=100.05):
    return {
        "provider": "IBKR_TWS_API", "market_data_type": market_type,
        "entitlement_confirmed": True, "rights_confirmed": True,
        "session_authenticated": True,
        "contract_id": 1234567, "isin": INSTRUMENT["isin"],
        "symbol": INSTRUMENT["symbol"], "listing_mic": "XSTO", "currency": "SEK",
        "trade_venue_mic": "XSTO", "book_venue_mic": "XSTO",
        "exchange_mapping_confirmed": True, "market_phase": "CONTINUOUS",
        "trade_ts_utc": (NOW-timedelta(seconds=3)).isoformat(),
        "bid_ask_ts_utc": (NOW-timedelta(seconds=2)).isoformat(),
        "received_at_utc": (NOW-timedelta(seconds=1)).isoformat(),
        "last": 100, "bid": ask-0.15, "ask": ask,
    }


def grade():
    return {
        "status": "ANALYZED_INDICATIVE_SETUP", "opportunity_grade": "VERY_GOOD",
        "score": 90, "entry_price": 100, "lowest_sell_point": 98,
        "sell_point": 106,
        "chart_as_of": (NOW-timedelta(minutes=5)).isoformat(),
        "observed_turnover_proxy_sek": 12_000_000,
        "why": ["Kursen över medelvärdet", "Hög relativ volym"],
        "risks": ["Spread och kursgap", "Historisk motståndsnivå"],
        "source_news_opinion_used": False, "actionable": False
    }


def quality(**kwargs):
    return evaluate_primary_live_quote(
        {**raw_quote(), **kwargs}, INSTRUMENT, now=NOW
    )


def test_live_recheck_gives_all_requested_levels_in_swedish():
    snapshot = quality()
    assert snapshot.accepted_as_primary_live
    report = build_live_alert(INSTRUMENT, grade(), snapshot, now=NOW)
    assert report["ready_for_preview"]
    text = report["message"]
    assert "MYCKET GOD PRELIMINÄR" in text
    for term in ["köp/ask", "stop-loss", "Målkurs", "Potential",
                 "Risk/reward", "VARFÖR", "RISKER", "Avanza"]:
        assert term in text
    assert "100.05 kr" in text
    assert "98.00 kr" in text and "106.00 kr" in text
    assert report["auto_order_enabled"] is False


def test_delayed_provider_blocked_from_telegram():
    result = build_live_alert(
        INSTRUMENT, grade(), quality(market_data_type=3), now=NOW
    )
    assert not result["ready_for_preview"]
    assert "message" not in result


def test_real_time_price_jump_invalidates_trade():
    result = build_live_alert(
        INSTRUMENT, grade(), quality(last=102, bid=102, ask=102.1), now=NOW
    )
    assert not result["ready_for_preview"]


def test_missing_observed_liquidity_blocks_telegram():
    a = grade()
    a.pop("observed_turnover_proxy_sek")
    result = build_live_alert(INSTRUMENT, a, quality(), now=NOW)
    assert not result["ready_for_preview"]
    assert result["reason"] == "missing_or_low_observed_liquidity"


def test_publisher_opinion_is_not_analyst_evidence():
    a = grade()
    a["source_news_opinion_used"] = True
    assert not build_live_alert(INSTRUMENT, a, quality(), now=NOW)[
        "ready_for_preview"]


def test_unverified_quote_wrong_xsto_market_cannot_alert():
    snap = raw_quote()
    snap["trade_venue_mic"] = "CHIX"
    gate = evaluate_primary_live_quote(snap, INSTRUMENT, now=NOW)
    assert not build_live_alert(INSTRUMENT, grade(), gate, now=NOW)[
        "ready_for_preview"]


def test_stale_historical_chart_blocks_telegram():
    a = grade()
    a["chart_as_of"] = (NOW-timedelta(minutes=35)).isoformat()
    assert not build_live_alert(INSTRUMENT, a, quality(), now=NOW)[
        "ready_for_preview"]


def test_invalid_identity_blocks_telegram():
    incorrect = deepcopy(INSTRUMENT)
    incorrect["isin"] = "SE0021628898"
    assert not build_live_alert(incorrect, grade(), quality(), now=NOW)[
        "ready_for_preview"]
