"""Authorized manifest is a prerequisite for broad XSTO scan planning."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from src.stockholm_universe_batch import create_batch_plan, audit_sweep

NOW = datetime(2026, 10, 21, 15, tzinfo=timezone.utc)


def manifests():
    listings = [
        ("SE0000000001", "ALPHA", "Large Cap", "1"),
        ("SE0000000002", "BRAVO", "Mid Cap", "2"),
        ("SE0000000003", "CHARLIE", "Small Cap", "3"),
        ("SE0000000004", "DELTA", "Large Cap", "4"),
        ("SE0000000005", "ECHO", "Small Cap", "5"),
        ("SE0000000006", "FOXTROT", "Large Cap", "6"),
        ("SE0000000007", "GOLF", "Mid Cap", "7"),
    ]
    rows = [{"isin": isin, "symbol": symbol, "mic": "XSTO", "segment": segment}
            for isin, symbol, segment, book in listings]
    mapped = [
        {**row, "order_book_id": book, "currency": "SEK",
         "instrument_type": "EQUITY", "active": True}
        for row, (_, _, _, book) in zip(rows, listings)
    ]
    ref = {"source": "operator-authorized-reference", "as_of": NOW.isoformat(),
           "source_verified": True, "complete_main_market": True,
           "listings": rows}
    mapping = {"source": "independent-avanza-mapping", "as_of": NOW.isoformat(),
               "listings": mapped}
    return ref, mapping


def test_every_instrument_scheduled_once_across_bounded_batches():
    ref, mapping = manifests()
    plans = [create_batch_plan(ref, mapping, index=i, size=3, now=NOW)
             for i in range(3)]
    assert plans[0].batch_size == 3
    assert plans[0].batch_count == 3
    assert {r["segment"] for r in plans[0].stocks} == {
        "Large Cap", "Mid Cap", "Small Cap"}
    assert all(p.reference_hash == plans[0].reference_hash for p in plans)
    assert audit_sweep(plans, expected_total=7, expected_hash=plans[0].reference_hash)[
        "all_reference_instruments_scheduled"]


def test_partial_batches_never_claim_complete_coverage():
    ref, mapping = manifests()
    first = create_batch_plan(ref, mapping, index=0, size=3, now=NOW)
    result = audit_sweep([first], expected_total=7, expected_hash=first.reference_hash)
    assert result["stocks_seen"] == 3
    assert result["all_reference_instruments_scheduled"] is False
    assert result["all_market_prices_verified"] is False


def test_no_duplicate_scan_batch():
    ref, mapping = manifests()
    first = create_batch_plan(ref, mapping, index=0, size=3, now=NOW)
    with pytest.raises(ValueError, match="duplicate"):
        audit_sweep([first, first], expected_total=7,
                    expected_hash=first.reference_hash)


def test_stale_reference_and_missing_listing_rejected():
    ref, mapping = manifests()
    mapping["listings"].pop()
    with pytest.raises(ValueError, match="not_completely_verified"):
        create_batch_plan(ref, mapping, index=0, now=NOW)
    ref, mapping = manifests()
    ref["source_verified"] = False
    with pytest.raises(ValueError, match="not_completely_verified"):
        create_batch_plan(ref, mapping, index=0, now=NOW)


def test_batches_protect_rate_limits():
    ref, mapping = manifests()
    with pytest.raises(ValueError, match="invalid_batch_bounds"):
        create_batch_plan(ref, mapping, index=0, size=100, now=NOW)
    with pytest.raises(ValueError, match="batch_index_out_of_range"):
        create_batch_plan(ref, mapping, index=1, size=12, now=NOW)
