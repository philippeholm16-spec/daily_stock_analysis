"""No stale or venue-mismatched IBKR quote can be treated as XSTO real-time."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from src.ibkr_tws_quote_adapter import (
    build_ibkr_tws_snapshot, instrument_from_ibkr_contract
)
from src.stockholm_realtime_quality import evaluate_primary_live_quote


NOW = datetime(2026, 10, 22, 7, 30, 0, tzinfo=timezone.utc)
CONTRACT = {
    "conId": 1234567, "isin": "SE0000115446",
    "symbol": "VOLV B", "listing_mic": "XSTO",
    "currency": "SEK", "identity_verified": True,
}
TRADE = {"time": (NOW - timedelta(seconds=4)).timestamp(),
         "price": 325.0, "exchange": "SFB"}
BOOK = {"time": (NOW - timedelta(seconds=2)).timestamp(),
        "bid": 324.9, "ask": 325.0}
SESSION = {
    "marketDataType": 1, "nordic_l1_active": True,
    "bot_analytics_rights_approved": True, "authenticated": True,
    "direct_book_exchange": "SFB", "exchange_mapping_verified": True,
    "book_venue_proof_observed": True,
    "market_phase": "CONTINUOUS"
}
EXCHANGE_MAP = {"SFB": "XSTO", "CBOE": "CHIX"}


def live():
    instrument = instrument_from_ibkr_contract(CONTRACT)
    snap = build_ibkr_tws_snapshot(
        CONTRACT, TRADE, BOOK, SESSION,
        received_at=NOW-timedelta(seconds=1),
        confirmed_exchange_map=EXCHANGE_MAP
    )
    return snap, instrument


def test_fully_verified_live_ibkr_fixture_passes_quote_gate_only():
    quote, instrument = live()
    result = evaluate_primary_live_quote(quote, instrument, now=NOW)
    assert result.accepted_as_primary_live
    assert result.quote["data_quality"] == "PRIMARY_XSTO_LIVE_QUOTE_VERIFIED"
    assert result.quote["actionable"] is False
    assert result.quote["trade_signal"] is None
    assert result.quote["ask"] == 325.0


def test_ibkr_delayed_market_data_type_is_rejected():
    quote, ident = live()
    quote["market_data_type"] = 3
    result = evaluate_primary_live_quote(quote, ident, now=NOW)
    assert not result.accepted_as_primary_live
    assert "unapproved_provider_or_non_live_data_type" in result.reasons


def test_ibkr_frozen_market_data_type_rejected():
    quote, ident = live()
    quote["market_data_type"] = 2
    assert not evaluate_primary_live_quote(quote, ident, now=NOW).accepted_as_primary_live


def test_entitlement_and_non_display_rights_explicit():
    quote, ident = live()
    quote["rights_confirmed"] = False
    result = evaluate_primary_live_quote(quote, ident, now=NOW)
    assert not result.accepted_as_primary_live
    assert "subscription_or_usage_rights_not_confirmed" in result.reasons


def test_cboe_europe_realtime_is_not_nasdaq_primary_trade():
    contract = deepcopy(CONTRACT)
    trade = deepcopy(TRADE)
    trade["exchange"] = "CBOE"
    snapshot = build_ibkr_tws_snapshot(
        contract, trade, BOOK, SESSION,
        received_at=NOW, confirmed_exchange_map=EXCHANGE_MAP
    )
    result = evaluate_primary_live_quote(
        snapshot, instrument_from_ibkr_contract(contract), now=NOW
    )
    assert not result.accepted_as_primary_live
    assert "nonprimary_or_unverified_venue" in result.reasons


def test_smart_venue_cannot_claim_xsto_book():
    session = deepcopy(SESSION)
    session["direct_book_exchange"] = "SMART"
    snap = build_ibkr_tws_snapshot(
        CONTRACT, TRADE, BOOK, session,
        received_at=NOW, confirmed_exchange_map={**EXCHANGE_MAP, "SMART": "XSTO"}
    )
    result = evaluate_primary_live_quote(
        snap, instrument_from_ibkr_contract(CONTRACT), now=NOW
    )
    assert not result.accepted_as_primary_live


def test_wrong_class_or_conid_rejected():
    snap, ident = live()
    ident["contract_id"] = 9999
    assert not evaluate_primary_live_quote(snap, ident, now=NOW).accepted_as_primary_live
    snap, ident = live()
    snap["isin"] = "SE0021628898"
    assert not evaluate_primary_live_quote(snap, ident, now=NOW).accepted_as_primary_live


def test_stale_trade_and_book_rejected_independently():
    snap, ident = live()
    snap["trade_ts_utc"] = (NOW - timedelta(minutes=15)).isoformat()
    reasons = evaluate_primary_live_quote(snap, ident, now=NOW).reasons
    assert "trade_stale" in reasons
    snap, ident = live()
    snap["bid_ask_ts_utc"] = (NOW - timedelta(seconds=30)).isoformat()
    reasons = evaluate_primary_live_quote(snap, ident, now=NOW).reasons
    assert "bid_ask_stale" in reasons


def test_missing_exchange_timestamp_is_not_inferred_from_receipt():
    snap, ident = live()
    snap["trade_ts_utc"] = None
    assert "trade_timestamp_missing" in evaluate_primary_live_quote(
        snap, ident, now=NOW).reasons


def test_stale_transport_and_crossed_book_rejected():
    snap, ident = live()
    snap["received_at_utc"] = (NOW-timedelta(minutes=2)).isoformat()
    assert not evaluate_primary_live_quote(snap, ident, now=NOW).accepted_as_primary_live
    snap, ident = live()
    snap["bid"] = 325.5
    assert "crossed_or_locked_book" in evaluate_primary_live_quote(
        snap, ident, now=NOW).reasons


def test_outside_session_and_halt_rejected():
    snap, ident = live()
    snap["market_phase"] = "HALTED"
    assert not evaluate_primary_live_quote(snap, ident, now=NOW).accepted_as_primary_live
    snap, ident = live()
    assert "outside_regular_stockholm_session" in evaluate_primary_live_quote(
        snap, ident, now=datetime(2026, 10, 24, 7, 30, tzinfo=timezone.utc)
    ).reasons


def test_fixture_contract_resolution_is_mandatory():
    c = deepcopy(CONTRACT)
    c["identity_verified"] = False
    try:
        instrument_from_ibkr_contract(c)
    except ValueError as exc:
        assert "unverified" in str(exc)
    else:
        raise AssertionError("unverified contract must not be accepted")


def test_provider_must_be_ibkr_realtime_authenticated_not_unofficial_avanza():
    snap, ident = live()
    snap["provider"] = "UNOFFICIAL_AVANZA_MCP"
    assert not evaluate_primary_live_quote(snap, ident, now=NOW).accepted_as_primary_live


def test_direct_book_venue_cannot_be_fabricated_from_contract():
    session = deepcopy(SESSION)
    session["book_venue_proof_observed"] = False
    quote = build_ibkr_tws_snapshot(
        CONTRACT, TRADE, BOOK, session,
        received_at=NOW, confirmed_exchange_map=EXCHANGE_MAP
    )
    gate = evaluate_primary_live_quote(
        quote, instrument_from_ibkr_contract(CONTRACT), now=NOW
    )
    assert not gate.accepted_as_primary_live
    assert "nonprimary_or_unverified_venue" in gate.reasons
