"""Read-only ISIN discovery: verify unique conId before live subscription."""
from types import SimpleNamespace
import pytest

from scripts.ibkr_contract_lookup import resolve_unique_contract, lookup_local


ISIN = "SE0000115446"


def contract(conid, *, isin=ISIN, secid_field="key", currency="SEK"):
    ids = ([{secid_field: "ISIN", "value": isin}]
           if isin is not None else [])
    return {
        "contract": {"conId": conid, "symbol": "VOLV",
                     "localSymbol": "VOLV B", "secType": "STK",
                     "currency": currency, "primaryExchange": "SFB"},
        "secIdList": ids,
    }


def test_one_matching_swedish_equity_gets_resolved():
    output = resolve_unique_contract([contract(76543)], isin=ISIN)
    assert output["resolved"]
    assert output["instrument"]["conid"] == 76543
    assert not output["instrument"]["listing_venue_verified"]


def test_duplicate_same_conid_does_not_trigger_multiple_share_classes():
    output = resolve_unique_contract([contract(76543),
                                      contract(76543, secid_field="tag")],
                                     isin=ISIN)
    assert output["resolved"]


def test_two_matching_conids_need_manual_exchange_review():
    output = resolve_unique_contract([contract(76543), contract(76544)], isin=ISIN)
    assert not output["resolved"]
    assert output["reason"] == "multiple_matching_share_contracts"


def test_unverified_isin_or_wrong_currency_cannot_resolve():
    output = resolve_unique_contract([contract(76543, isin=None)], isin=ISIN)
    assert not output["resolved"]
    output = resolve_unique_contract([contract(76543, currency="EUR")], isin=ISIN)
    assert not output["resolved"]


def test_invalid_local_arguments_fail_before_any_api_login():
    with pytest.raises(ValueError, match="invalid_local"):
        lookup_local(isin="VOLV B")
    with pytest.raises(ValueError, match="invalid_local"):
        lookup_local(isin=ISIN, port=9001)
