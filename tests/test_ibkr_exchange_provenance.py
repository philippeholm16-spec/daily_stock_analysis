"""Proof of quote venue uses IBKR's returned 32/33 SmartComponents."""
from src.ibkr_exchange_provenance import (
    decode_smart_components, verify_direct_primary_book,
)


COMPONENTS = [
    {"letter": "A", "exchange": "SFB"},
    {"letter": "B", "exchange": "CBOE"},
]


def test_actual_bid_and_ask_component_codes_prove_both_primary():
    proof = verify_direct_primary_book(
        "A", "A", COMPONENTS, expected_provider_exchange="SFB"
    )
    assert proof.verified
    assert proof.bid_exchange == proof.ask_exchange == "SFB"


def test_primary_listing_or_direct_route_alone_cannot_prove_venue():
    missing = verify_direct_primary_book(
        None, None, COMPONENTS, expected_provider_exchange="SFB"
    )
    assert not missing.verified
    assert missing.reason == "missing_bid_or_ask_exchange"


def test_one_other_venue_blocks():
    other = verify_direct_primary_book(
        "A", "B", COMPONENTS, expected_provider_exchange="SFB"
    )
    assert not other.verified
    assert other.reason == "not_primary_exchange"


def test_consolidated_smart_book_is_not_exchange_specific():
    mix = verify_direct_primary_book(
        "AB", "A", COMPONENTS, expected_provider_exchange="SFB"
    )
    assert not mix.verified
    assert mix.reason == "multi_venue_consolidated_book"


def test_unknown_component_fails():
    proof = verify_direct_primary_book(
        "Z", "Z", COMPONENTS, expected_provider_exchange="SFB"
    )
    assert not proof.verified
    assert proof.reason == "unmapped_quote_venue"


def test_ambiguous_letter_map_rejected():
    items = COMPONENTS + [{"letter": "A", "exchange": "CBOE"}]
    proof = verify_direct_primary_book(
        "A", "A", items, expected_provider_exchange="SFB"
    )
    assert not proof.verified


def test_decode_ibkr_object_callback_format():
    class Component:
        def __init__(self, exchangeLetter, exchange):
            self.exchangeLetter = exchangeLetter
            self.exchange = exchange
    result = decode_smart_components([
        Component("Q", "SFB"),
        Component("X", "CHIX"),
    ])
    assert result == {"Q": "SFB", "X": "CHIX"}


def test_smart_not_primary():
    proof = verify_direct_primary_book(
        "A", "A", COMPONENTS, expected_provider_exchange="SMART"
    )
    assert not proof.verified
    assert proof.reason == "invalid_primary_provider_exchange"
