from datetime import datetime, timedelta, timezone

import pytest

from src.swedish_market_universe import (
    Listing, UniverseError, UniverseSnapshot, validate_universe,
)


NOW = datetime(2026, 10, 21, 9, 0, tzinfo=timezone.utc)


def snapshot(**overrides):
    data = dict(
        source="verified_provider_snapshot",
        as_of=NOW,
        complete_main_market=True,
        listings=(Listing("SE0000000000", "EXAMPLE-A", "XSTO",
                          "Large Cap", "SEK", "EQUITY", True),),
    )
    data.update(overrides)
    return UniverseSnapshot(**data)


def test_valid_snapshot():
    assert len(validate_universe(snapshot(), now=NOW)) == 1


@pytest.mark.parametrize("changes", [
    {"source": ""},
    {"complete_main_market": False},
    {"listings": ()},
    {"as_of": NOW - timedelta(hours=25)},
    {"as_of": NOW + timedelta(seconds=1)},
    {"as_of": NOW.replace(tzinfo=None)},
])
def test_invalid_snapshot_rejected(changes):
    with pytest.raises(UniverseError):
        validate_universe(snapshot(**changes), now=NOW)


@pytest.mark.parametrize("changes", [
    {"mic": "XHEL"},
    {"segment": "First North"},
    {"currency": "EUR"},
    {"instrument_type": "ETF"},
    {"active": False},
    {"symbol": ""},
])
def test_invalid_listing_rejected(changes):
    original = snapshot().listings[0]
    from dataclasses import replace
    with pytest.raises(UniverseError):
        validate_universe(snapshot(listings=(replace(original, **changes),)), now=NOW)


def test_duplicate_listing_rejected():
    original = snapshot().listings[0]
    with pytest.raises(UniverseError):
        validate_universe(snapshot(listings=(original, original)), now=NOW)
