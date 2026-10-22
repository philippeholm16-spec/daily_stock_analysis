"""The book's execution venue may not be inferred from another feed."""
from src.ibkr_book_corroboration import verify_streaming_book


def bbo(**kwargs):
    params = {
        "stream_bid": 100.0, "stream_ask": 100.05,
        "tick_bid": 100.0, "tick_ask": 100.05,
        "min_tick": 0.01,
        "streaming_bid_age": 1.0, "streaming_ask_age": 1.0,
        "bid_venue_age": 2.0, "ask_venue_age": 2.0
    }
    return verify_streaming_book(**{**params, **kwargs})


def test_identical_two_stream_bbo_is_corroborated():
    output = bbo()
    assert output.verified
    assert output.primary_bid == 100.0 and output.primary_ask == 100.05


def test_tickbytick_price_from_different_book_is_rejected():
    result = bbo(tick_bid=99.50)
    assert not result.verified
    assert result.reason == "tick_and_primary_bbo_disagree"


def test_tiny_quote_move_one_tick_tolerance():
    result = bbo(tick_bid=99.99)
    assert result.verified


def test_old_price_but_fresh_tick_is_not_a_live_primary_bbo():
    result = bbo(streaming_bid_age=45)
    assert result.reason == "stale_streaming_book_update"


def test_missing_exchange_code_age_rejected():
    result = bbo(ask_venue_age=None)
    assert result.reason == "stale_or_missing_exchange_venue_codes"


def test_venue_code_too_old_rejected():
    result = bbo(bid_venue_age=70)
    assert result.reason == "stale_or_missing_exchange_venue_codes"


def test_locked_or_crossed_stream_quote_rejected():
    result = bbo(stream_bid=100.20)
    assert result.reason == "locked_or_crossed_book"


def test_unknown_tick_or_invalid_min_tick_rejected():
    assert bbo(tick_bid=None).reason == "missing_or_invalid_streaming_book"
    assert bbo(min_tick=0).reason == "missing_or_invalid_streaming_book"


def test_bool_price_never_cast_to_numeric():
    assert not bbo(stream_bid=True).verified
