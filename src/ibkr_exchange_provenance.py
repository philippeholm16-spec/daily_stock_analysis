"""Resolve IBKR BBO venue provenance through actual SmartComponents callbacks.

IBKR tickByTickBidAsk has a bid and an ask, but NO exchange field.
tickString fields 32 and 33 show *encoded* bidExch/askExch letters and
require a contract-specific reqSmartComponents map (obtained from
tickReqParams). Inferring XSTO directly from Contract.exchange is unsafe.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class VenueProof:
    verified: bool
    reason: str
    bid_exchange: str | None = None
    ask_exchange: str | None = None


def decode_smart_components(components):
    """Convert IBKR SmartComponent callbacks into letter -> exchange mapping.

    A component contains exchangeLetter and exchange. Reject ambiguous maps.
    An exchange can have multiple letters, but a letter cannot name multiple
    different exchanges. Do not guess missing components.
    """
    if not isinstance(components, list) or not components:
        raise ValueError("unavailable_smart_components")
    result = {}
    for component in components:
        letter = component.get("letter") if isinstance(component, dict) else getattr(component, "exchangeLetter", None)
        exchange = component.get("exchange") if isinstance(component, dict) else getattr(component, "exchange", None)
        if not isinstance(letter, str) or len(letter) != 1 or not letter.isalpha():
            raise ValueError("invalid_component_letter")
        if not isinstance(exchange, str) or not exchange.strip():
            raise ValueError("invalid_component_exchange")
        if letter in result and result[letter] != exchange:
            raise ValueError("ambiguous_component_exchange")
        result[letter] = exchange
    return result


def verify_direct_primary_book(bid_codes, ask_codes, components,
                               *, expected_provider_exchange):
    """Conservatively require bid AND ask solely from verified direct venue.

    Multi-letter codes imply multiple components at the best price; do not
    treat such SMART/consolidated bid/ask as verified XSTO primary book.
    External proof is still needed that expected_provider_exchange maps
    to MIC=XSTO for this instrument and contract.
    """
    if (not isinstance(expected_provider_exchange, str)
            or not expected_provider_exchange or
            expected_provider_exchange.upper() == "SMART"):
        return VenueProof(False, "invalid_primary_provider_exchange")
    try:
        mapping = decode_smart_components(components)
    except ValueError:
        return VenueProof(False, "missing_or_ambiguous_exchange_components")
    if not isinstance(bid_codes, str) or not isinstance(ask_codes, str):
        return VenueProof(False, "missing_bid_or_ask_exchange")
    if len(bid_codes) != 1 or len(ask_codes) != 1:
        return VenueProof(False, "multi_venue_consolidated_book")
    bid = mapping.get(bid_codes)
    ask = mapping.get(ask_codes)
    if bid is None or ask is None:
        return VenueProof(False, "unmapped_quote_venue")
    if bid != expected_provider_exchange or ask != expected_provider_exchange:
        return VenueProof(False, "not_primary_exchange")
    return VenueProof(True, "both_book_sides_proven_direct_primary", bid, ask)
