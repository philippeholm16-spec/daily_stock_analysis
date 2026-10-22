"""IBKR ContractDetails identity tests across Python API entry formats."""
from src.ibkr_contract_identity import extract_secids, verify_contract_details


CONID = 100123
ISIN = "SE0000115446"


class Field:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def detail(ids, *, security_type="STK", currency="SEK", conid=CONID):
    return Field(
        contract=Field(conId=conid, symbol="VOLV", localSymbol="VOLV B",
                       secType=security_type, currency=currency,
                       primaryExchange="SFB"),
        secIdList=ids,
    )


def test_ibkr_modern_key_value_contract_details():
    result = verify_contract_details(
        detail([Field(key="ISIN", value=ISIN)]), expected_isin=ISIN,
        expected_conid=CONID
    )
    assert result["conid"] == CONID and result["isin"] == ISIN
    assert result["isin_verified_by_contract_details"]
    assert result["listing_venue_verified"] is False


def test_ibkr_legacy_tag_value_contract_details():
    result = verify_contract_details(
        detail([Field(tag="ISIN", value=ISIN)]), expected_isin=ISIN)
    assert result is not None


def test_dict_based_secids():
    result = extract_secids({"secIdList": [{"key": "ISIN", "value": ISIN}]})
    assert result == {"ISIN": ISIN}


def test_missing_sec_id_never_guesstimates_identity_from_symbol():
    result = verify_contract_details(detail([]), expected_isin=ISIN)
    assert result is None


def test_conflicting_isins_or_wrong_class_fail_closed():
    both = detail([Field(key="ISIN", value=ISIN),
                   Field(key="ISIN", value="SE0021628898")])
    assert verify_contract_details(both, expected_isin=ISIN) is None
    assert verify_contract_details(detail([Field(tag="ISIN", value=ISIN)],
                                          security_type="FUT"), expected_isin=ISIN) is None
    assert verify_contract_details(detail([Field(tag="ISIN", value=ISIN)],
                                          currency="EUR"), expected_isin=ISIN) is None


def test_wrong_conid_or_wrong_isin_fails():
    valid = detail([Field(tag="ISIN", value=ISIN)])
    assert verify_contract_details(valid, expected_isin=ISIN,
                                   expected_conid=CONID+1) is None
    assert verify_contract_details(valid, expected_isin="SE0021628898") is None


def test_no_unverified_primary_exchange_claim():
    ident = verify_contract_details(
        detail([Field(key="ISIN", value=ISIN)]), expected_isin=ISIN)
    assert ident["primary_exchange_unverified"] == "SFB"
    assert ident["listing_venue_verified"] is False
