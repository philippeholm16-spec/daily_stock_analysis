"""Isolated quality gate tests; no network access."""
import pytest
from src.avanza_batch_quality import validate_quotes


def test_complete_batch_but_not_actionable():
    c, good, bad = validate_quotes(["5269", "1296604"], [
        {"order_book_id": "5269", "last": 320.5, "totalVolumeTraded": 1049844.0, "isRealTime": False},
        {"order_book_id": "1296604", "last": 11.2, "totalVolumeTraded": 1000.0, "isRealTime": True},
    ])
    assert c.complete and c.valid == 2 and c.realtime == 1
    assert not bad
    assert all(not item["actionable"] for item in good.values())


def test_missing_quote_fails_closed():
    c, good, bad = validate_quotes(["5269", "1296604"], [
        {"order_book_id": "5269", "last": 320.5, "totalVolumeTraded": 100.0}
    ])
    assert not c.complete and bad["1296604"] == "missing_quote"


def test_bad_price_rejected():
    c, good, bad = validate_quotes(["5269"], [
        {"order_book_id": "5269", "last": -1, "totalVolumeTraded": 100.0}
    ])
    assert not c.complete and not good and bad["5269"]


def test_duplicate_provider_response_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        validate_quotes(["5269"], [
            {"order_book_id": "5269", "last": 1, "totalVolumeTraded": 1},
            {"order_book_id": "5269", "last": 2, "totalVolumeTraded": 2},
        ])
