"""IBKR TWS tick-by-tick event adapter, read-only and credential-free.

The event collector must use reqMarketDataType(1) and licensed Nordic L1,
resolve IBKR contract details by conId + ISIN, and request direct-routed
XSTO venue rather than accepting SMART/Cboe consolidated prices.

Use historical exchange mapping or reqSmartComponents only when explicitly
validated. Never derive execution venue from the ticker's listing venue.
"""
from datetime import datetime, timezone
from math import isfinite


def _stamp_from_unix(raw):
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not isfinite(raw):
        return None
    # IBKR tickByTickAllLast and tickByTickBidAsk return Unix *seconds*.
    if not 1_500_000_000 <= raw <= 4_000_000_000:
        return None
    return datetime.fromtimestamp(raw, timezone.utc).isoformat()


def build_ibkr_tws_snapshot(contract, last_tick, book_tick, session, *,
                            received_at,
                            confirmed_exchange_map):
    """Transform IBKR callback payloads into the strict primary-live gate.

    contract: authorized conId, ISIN, listing symbol, currency and venue.
    last_tick: tickByTickAllLast(time, price, exchange)
    book_tick: tickByTickBidAsk(time, bid, ask)
    session: marketDataType callback and observed authenticated entitlements.
    confirmed_exchange_map: mapping from live IBKR vendor market codes to MIC.
    No I/O. Cannot on its own verify credentials or exchange entitlement.
    """
    if not all(isinstance(x, dict) for x in
               (contract, last_tick, book_tick, session, confirmed_exchange_map)):
        raise ValueError("invalid_ibkr_callback_payload")
    trade_exchange = last_tick.get("exchange")
    book_exchange = session.get("direct_book_exchange")
    trade_mic = confirmed_exchange_map.get(trade_exchange)
    book_mic = confirmed_exchange_map.get(book_exchange)
    # An explicit, separately verified direct-book venue is required;
    # SMART does not prove venue XSTO.
    mapping_ok = (session.get("exchange_mapping_verified") is True
                  and isinstance(trade_exchange, str)
                  and isinstance(book_exchange, str)
                  and book_exchange.upper() != "SMART"
                  and trade_mic == "XSTO" and book_mic == "XSTO")
    if not isinstance(received_at, datetime) or received_at.tzinfo is None:
        raise ValueError("missing_authenticated_receive_timestamp")
    return {
        "provider": "IBKR_TWS_API",
        "market_data_type": session.get("marketDataType"),
        "entitlement_confirmed": session.get("nordic_l1_active") is True,
        "rights_confirmed": session.get("bot_analytics_rights_approved") is True,
        "session_authenticated": session.get("authenticated") is True,
        "contract_id": contract.get("conId"),
        "isin": contract.get("isin"),
        "symbol": contract.get("symbol"),
        "listing_mic": contract.get("listing_mic"),
        "currency": contract.get("currency"),
        "trade_venue_mic": trade_mic,
        "book_venue_mic": book_mic,
        "exchange_mapping_confirmed": mapping_ok,
        "market_phase": session.get("market_phase"),
        "trade_ts_utc": _stamp_from_unix(last_tick.get("time")),
        "bid_ask_ts_utc": _stamp_from_unix(book_tick.get("time")),
        "received_at_utc": received_at.astimezone(timezone.utc).isoformat(),
        "last": last_tick.get("price"),
        "bid": book_tick.get("bid"),
        "ask": book_tick.get("ask"),
    }


def instrument_from_ibkr_contract(contract):
    """Require authenticated contractDetails resolution, not fuzzy symbol search."""
    if not isinstance(contract, dict) or contract.get("identity_verified") is not True:
        raise ValueError("unverified_ibkr_contract_details")
    return {
        "contract_id": contract.get("conId"),
        "isin": contract.get("isin"),
        "symbol": contract.get("symbol"),
        "listing_mic": contract.get("listing_mic"),
    }
