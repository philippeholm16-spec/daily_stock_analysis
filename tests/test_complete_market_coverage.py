"""Offline XSTO coverage audit tests, independent source not implicitly trusted."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta

from src.complete_market_coverage import audit_complete_xsto


NOW = datetime(2026, 10, 21, 16, tzinfo=timezone.utc)
REF_ROW = {"isin": "SE0000115446", "symbol": "VOLV B", "mic": "XSTO",
           "segment": "Large Cap"}
MAPPED_ROW = {**REF_ROW, "order_book_id": "5269",
              "active": True, "instrument_type": "EQUITY"}


def datasets():
    return (
        {"source": "authorized-nasdaq-reference", "source_verified": True,
         "complete_main_market": True, "as_of": NOW.isoformat(),
         "listings": [deepcopy(REF_ROW)]},
        {"source": "avanza-order-book-ids", "as_of": NOW.isoformat(),
         "listings": [deepcopy(MAPPED_ROW)]},
    )


def test_exact_independently_claimed_snapshot_matches():
    ref, mapping = datasets()
    out = audit_complete_xsto(ref, mapping, now=NOW)
    assert out.complete
    assert out.reference_count == 1 and out.mapped_count == 1
    # This is an artificial complete sample. Never use it as a full universe.


def test_missing_class_fails_and_reports_missing_isin():
    ref, mapping = datasets()
    mapping["listings"] = []
    out = audit_complete_xsto(ref, mapping, now=NOW)
    assert not out.complete and out.missing_isins == ("SE0000115446",)


def test_ticker_mismatch_fails():
    ref, mapping = datasets()
    mapping["listings"][0]["symbol"] = "VOLCAR B"
    result = audit_complete_xsto(ref, mapping, now=NOW)
    assert not result.complete and result.mismatched == ("SE0000115446",)


def test_order_book_id_duplicate_is_fatal():
    ref, mapping = datasets()
    another = {**MAPPED_ROW, "isin": "SE0021628898", "symbol": "VOLCAR B"}
    ref["listings"].append({"isin": another["isin"], "symbol": another["symbol"],
                             "mic": "XSTO", "segment": "Large Cap"})
    mapping["listings"].append(another)
    out = audit_complete_xsto(ref, mapping, now=NOW)
    assert not out.complete
    assert any("duplicate_order_book_id" in x for x in out.invalid_rows)


def test_reference_stale_or_same_source_fails():
    ref, mapping = datasets()
    ref["as_of"] = (NOW - timedelta(days=2)).isoformat()
    assert not audit_complete_xsto(ref, mapping, now=NOW).complete
    ref["as_of"] = NOW.isoformat()
    mapping["source"] = ref["source"]
    assert not audit_complete_xsto(ref, mapping, now=NOW).complete


def test_false_attestation_never_claims_complete():
    ref, mapping = datasets()
    ref["source_verified"] = False
    assert not audit_complete_xsto(ref, mapping, now=NOW).complete
    ref["source_verified"] = True
    ref["complete_main_market"] = False
    assert not audit_complete_xsto(ref, mapping, now=NOW).complete


def test_extra_delisted_or_wrong_market_cannot_pass():
    ref, mapping = datasets()
    mapping["listings"][0]["mic"] = "FNSE"
    assert not audit_complete_xsto(ref, mapping, now=NOW).complete
    mapping["listings"][0]["mic"] = "XSTO"
    mapping["listings"][0]["active"] = False
    assert not audit_complete_xsto(ref, mapping, now=NOW).complete
