"""No full-market scan without independently attested current Nasdaq reference."""
import json
from datetime import datetime, timezone
import pytest

from src.complete_market_coverage import audit_complete_xsto
from scripts.avanza_full_market import load_manifest


def source_docs():
    stamp = datetime.now(timezone.utc).isoformat()
    mapping = {
        "source": "Avanza public read-only order-book map",
        "source_verified": True, "complete_main_market": True,
        "as_of": stamp, "listings": [
            {"isin": "SE0003849223", "symbol": "BULTEN",
             "order_book_id": "290011", "segment": "Small Cap",
             "mic": "XSTO", "currency": "SEK",
             "instrument_type": "EQUITY", "active": True},
        ]
    }
    independent = {
        "source": "authorized independent XSTO reference",
        "source_verified": True, "complete_main_market": True,
        "as_of": stamp, "listings": [
            {"isin": "SE0003849223", "symbol": "BULTEN",
             "segment": "Small Cap", "mic": "XSTO"},
        ],
    }
    return independent, mapping


def test_verified_provenance_fixtures_can_pass_structural_audit(tmp_path):
    reference, mapping = source_docs()
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(mapping))
    _, rows = load_manifest(path)
    assert len(rows) == 1
    # The fixture is synthetic; this only proves the validator mechanics.
    assert audit_complete_xsto(reference, mapping).complete


def test_unverified_source_rejected_even_with_matching_rows():
    reference, mapping = source_docs()
    reference["source_verified"] = False
    assert not audit_complete_xsto(reference, mapping).complete


def test_incomplete_manifest_never_claims_full_market(tmp_path):
    _, mapping = source_docs()
    mapping["complete_main_market"] = False
    path = tmp_path / "incomplete.json"
    path.write_text(json.dumps(mapping))
    with pytest.raises(ValueError, match="complete_market_coverage_not_asserted"):
        load_manifest(path)


def test_wrong_xsto_symbol_blocks_coverage():
    reference, mapping = source_docs()
    mapping["listings"][0]["symbol"] = "BMAX"
    result = audit_complete_xsto(reference, mapping)
    assert not result.complete
    assert result.mismatched == ("SE0003849223",)
