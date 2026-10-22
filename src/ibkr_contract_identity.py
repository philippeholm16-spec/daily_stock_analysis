"""Strict IBKR contract/share-class identity from TWS ContractDetails.

The TWS API may expose secIdList rows as {tag,value}, {key,value},
TagValue objects, or SecIdListEntry objects. Verify the actual ISIN,
security type, currency, and positive unique conId. Do not infer ISIN from
a stock symbol or from a broker's internal conId.
"""
import re


ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")


def _field(raw, name):
    return raw.get(name) if isinstance(raw, dict) else getattr(raw, name, None)


def extract_secids(detail):
    secids = _field(detail, "secIdList")
    if not isinstance(secids, (list, tuple)):
        return {}
    found = {}
    for item in secids:
        key = _field(item, "tag") or _field(item, "key")
        val = _field(item, "value")
        if not isinstance(key, str) or not isinstance(val, str):
            continue
        label = key.upper().strip()
        if label in ("ISIN", "CUSIP", "FIGI"):
            if label in found and found[label] != val:
                raise ValueError("conflicting_contract_security_identifiers")
            found[label] = val
    return found


def verify_contract_details(detail, *, expected_isin, expected_conid=None):
    """Return identity object iff exact ISIN and local SEK equity confirmed.

    Unknown ISIN or ambiguous share class never passes. Exchange venue proof
    is a separate data-source check, not derived from primaryExchange here.
    """
    contract = _field(detail, "contract")
    if not isinstance(expected_isin, str) or not ISIN_PATTERN.fullmatch(expected_isin):
        raise ValueError("invalid_expected_isin")
    conid = _field(contract, "conId")
    if (isinstance(conid, bool) or not isinstance(conid, int) or conid <= 0
            or expected_conid is not None and conid != expected_conid):
        return None
    if _field(contract, "secType") != "STK" or _field(contract, "currency") != "SEK":
        return None
    try:
        identifiers = extract_secids(detail)
    except ValueError:
        return None
    if identifiers.get("ISIN") != expected_isin:
        return None
    return {
        "conid": conid, "isin": expected_isin,
        "ibkr_symbol": _field(contract, "symbol"),
        "local_symbol": _field(contract, "localSymbol"),
        "primary_exchange_unverified": _field(contract, "primaryExchange"),
        "currency": "SEK", "security_type": "STK",
        "isin_verified_by_contract_details": True,
        "listing_venue_verified": False,
    }
