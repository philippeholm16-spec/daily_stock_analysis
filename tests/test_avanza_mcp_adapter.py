from datetime import datetime, timezone

import pytest

from src.avanza_mcp_adapter import AvanzaDataError, parse_public_quote


def test_normalized_quote_is_never_actionable():
    quote = parse_public_quote(
        {"last_price": 100.5, "volume": 1234, "as_of": "2026-10-21T09:00:00+02:00"},
        order_book_id="123456",
    )
    assert quote.price == 100.5
    assert quote.as_of == datetime(2026, 10, 21, 7, tzinfo=timezone.utc)
    assert not quote.timestamp_verified and not quote.actionable


def test_missing_timestamp_does_not_create_fake_timestamp():
    quote = parse_public_quote({"last_price": 100, "volume": 0}, order_book_id="123")
    assert quote.as_of is None and not quote.actionable


@pytest.mark.parametrize("payload", [
    {"last_price": None, "volume": 5},
    {"last_price": 0, "volume": 5},
    {"last_price": float("nan"), "volume": 5},
    {"last_price": 10, "volume": None},
    {"last_price": 10, "volume": -1},
    {"last_price": 10, "volume": 1.5},
    {"last_price": 10, "volume": 1, "as_of": "yesterday"},
    {"last_price": 10, "volume": 1, "as_of": "2026-10-21T09:00:00"},
])
def test_bad_quote_rejected(payload):
    with pytest.raises(AvanzaDataError):
        parse_public_quote(payload, order_book_id="123")


def test_invalid_order_book_id_rejected():
    with pytest.raises(AvanzaDataError):
        parse_public_quote({"last_price": 10, "volume": 1}, order_book_id="not-an-id")
