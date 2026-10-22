"""Read-only localhost IBKR TWS/IB Gateway Nordic Level-1 diagnostic.

Use on the user's Mac with an authorized IBKR account and active subscription:
  pip install ibapi
  python -m scripts.ibkr_local_live_probe --conid 123456 --isin SE... \\
      --symbol "EXAMPLE B" --exchange-code <provider-confirmed-code>

This script NEVER calls placeOrder or reads account/positions. It does not
connect to GitHub Actions, Telegram, or a public host. IBKR TWS/Gateway
authentication is performed inside IBKR's own application.

A quote is not certified as XSTO realtime merely because the provider says
marketDataType=1. An authorized primary-venue exchange map, non-display
analytics rights and a current trading phase must also be confirmed. It is
normal for this diagnostic to return NOT_YET_VERIFIED.

Do not run continuously or expose IBKR Gateway's port to the internet.
"""
import argparse
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from src.ibkr_tws_quote_adapter import (
    build_ibkr_tws_snapshot, instrument_from_ibkr_contract
)
from src.stockholm_realtime_quality import evaluate_primary_live_quote
from src.ibkr_exchange_provenance import verify_direct_primary_book
from src.stockholm_live_alert import build_live_alert


def _iso():
    return datetime.now(timezone.utc)


def run_local_probe(*, conid, isin, symbol, exchange_code, port=7497,
                    client_id=77, duration_seconds=50,
                    exchange_map_verified=False, bot_rights_confirmed=False,
                    live_entitlement_confirmed=False,
                    analyst_result=None, capital_sek=15000):
    """One exact contract only. External ibapi installed by the user."""
    if (not isinstance(conid, int) or conid <= 0
            or not isinstance(isin, str) or len(isin) != 12
            or not isinstance(symbol, str) or not symbol.strip()
            or not isinstance(exchange_code, str) or not exchange_code.isalnum()
            or not 35 <= duration_seconds <= 90
            or port not in (7496, 7497, 4001, 4002)):
        raise ValueError("invalid_local_ibkr_probe_arguments")
    try:
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper
        from ibapi.contract import Contract
    except ImportError as exc:
        raise RuntimeError("ibapi_not_installed_on_local_mac") from exc

    contract = Contract()
    contract.conId = conid
    contract.secType = "STK"
    contract.currency = "SEK"
    contract.exchange = exchange_code

    class Reader(EWrapper, EClient):
        def __init__(self):
            EClient.__init__(self, self)
            self.contract_matches = []
            self.contract_details_end = False
            self.market_type = None
            self.last_tick = None
            self.book_tick = None
            self.isin_confirmed = False
            self.errors = []
            self.subscription_started = False
            self.book_subscription_started = False
            self.trade_subscription_start = None
            self.not_halted = None
            self.smart_components = []
            self.smart_map_requested = False
            self.bid_exchange_codes = None
            self.ask_exchange_codes = None
            self.finished = threading.Event()
            self.lock = threading.Lock()

        def nextValidId(self, orderId):
            # nextValidId is only a connection callback: no order is sent.
            self.reqContractDetails(501, contract)

        def contractDetails(self, reqId, details):
            if reqId != 501 or details.contract.conId != conid:
                return
            sec_id_list = getattr(details, "secIdList", None) or []
            tags = {getattr(x, "tag", ""): getattr(x, "value", "")
                    for x in sec_id_list}
            with self.lock:
                self.contract_matches.append({
                    "conid": details.contract.conId,
                    "localSymbol": getattr(details.contract, "localSymbol", None),
                    "primaryExchange": getattr(details.contract, "primaryExchange", None),
                    "validExchanges": getattr(details, "validExchanges", ""),
                })
                if tags.get("ISIN") == isin:
                    self.isin_confirmed = True

        def contractDetailsEnd(self, reqId):
            if reqId != 501:
                return
            self.contract_details_end = True
            with self.lock:
                matches = len(self.contract_matches)
            if matches != 1:
                self.errors.append("ambiguous_ibkr_contract_details")
                self.finished.set()
                return
            self.subscription_started = True
            self.reqMarketDataType(1)
            self.reqMktData(601, contract, "", False, False, [])
            self.reqTickByTickData(602, contract, "Last", 0, False)
            self.trade_subscription_start = time.monotonic()
            # IBKR rate-limits requests for the same instrument within 15 s.
            # The BidAsk request is started by the caller after >=16 sec.

        def marketDataType(self, reqId, marketDataType):
            if reqId == 601:
                with self.lock:
                    self.market_type = marketDataType

        def tickReqParams(self, tickerId, minTick, bboExchange, snapshotPermissions):
            if tickerId != 601 or not isinstance(bboExchange, str) or not bboExchange:
                return
            with self.lock:
                should_request = not self.smart_map_requested
                if should_request:
                    self.smart_map_requested = True
            if should_request:
                self.reqSmartComponents(701, bboExchange)

        def smartComponents(self, reqId, components):
            if reqId != 701:
                return
            with self.lock:
                self.smart_components = [
                    {"letter": getattr(part, "exchangeLetter", None),
                     "exchange": getattr(part, "exchange", None)}
                    for part in components
                ]

        def tickString(self, reqId, tickType, value):
            if reqId != 601:
                return
            with self.lock:
                if tickType == 32:
                    self.bid_exchange_codes = value
                elif tickType == 33:
                    self.ask_exchange_codes = value

        def tickGeneric(self, reqId, tickType, value):
            if reqId == 601 and tickType == 49:
                with self.lock:
                    self.not_halted = (value == 0)

        def tickByTickAllLast(self, reqId, tickType, time_, price, size,
                              tickAttribLast, exchange, specialConditions):
            if reqId != 602:
                return
            with self.lock:
                self.last_tick = {
                    "time": time_, "price": float(price),
                    "exchange": exchange,
                }

        def tickByTickBidAsk(self, reqId, time_, bidPrice, askPrice,
                             bidSize, askSize, tickAttribBidAsk):
            if reqId != 603:
                return
            with self.lock:
                self.book_tick = {
                    "time": time_, "bid": float(bidPrice),
                    "ask": float(askPrice),
                }

        def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
            # Log only numerical provider codes; no account or secret details.
            if errorCode not in (2104, 2106, 2158):
                self.errors.append("ibkr_error_code_" + str(errorCode))

    client = Reader()
    client.connect("127.0.0.1", port, client_id)
    if not client.isConnected():
        raise RuntimeError("ibkr_local_gateway_not_available")
    thread = threading.Thread(target=client.run, daemon=True)
    thread.start()
    start = time.monotonic()
    try:
        while time.monotonic() - start < duration_seconds:
            if (client.subscription_started and not client.book_subscription_started
                    and client.trade_subscription_start is not None
                    and time.monotonic() - client.trade_subscription_start >= 16):
                client.reqTickByTickData(603, contract, "BidAsk", 0, False)
                client.book_subscription_started = True
            with client.lock:
                complete = (client.market_type is not None
                            and client.last_tick is not None
                            and client.book_tick is not None)
            if complete or client.finished.is_set():
                break
            time.sleep(0.2)
        with client.lock:
            market_type = client.market_type
            trade = client.last_tick
            book = client.book_tick
            matches = list(client.contract_matches)
            isin_confirmed = client.isin_confirmed
            not_halted = client.not_halted
            bid_exchange_codes = client.bid_exchange_codes
            ask_exchange_codes = client.ask_exchange_codes
            smart_components = list(client.smart_components)
        venue_proof = verify_direct_primary_book(
            bid_exchange_codes, ask_exchange_codes, smart_components,
            expected_provider_exchange=exchange_code
        )
        info = {
            "provider": "IBKR_TWS_API",
            "requested_conid": conid,
            "contract_details_count": len(matches),
            "ibkr_market_data_type": market_type,
            "saw_trade_tick": trade is not None,
            "saw_bid_ask_tick": book is not None,
            "upstream_isin_confirmed": isin_confirmed,
            "operator_exchange_map_confirmed": exchange_map_verified,
            "subscription_confirmed": live_entitlement_confirmed,
            "provider_halt_status_observed": not_halted is not None,
            "venue_proof": venue_proof.reason,
            "bid_and_ask_primary_venue_observed": venue_proof.verified,
            "bot_analytics_rights_confirmed": bot_rights_confirmed,
            "errors": sorted(set(client.errors)),
            "live_primary_quote_verified": False,
            "reasons": ["insufficient_events_or_unverified_permissions"],
            "no_orders": True,
        }
        if trade is not None and book is not None:
            instrument = instrument_from_ibkr_contract({
                "conId": conid, "isin": isin, "symbol": symbol,
                "listing_mic": "XSTO", "identity_verified": isin_confirmed
            }) if isin_confirmed else None
            if instrument is None:
                info["reasons"] = ["exchange_contract_isin_not_proven"]
            else:
                session = {
                    "marketDataType": market_type,
                    "nordic_l1_active": live_entitlement_confirmed,
                    "bot_analytics_rights_approved": bot_rights_confirmed,
                    "authenticated": True,
                    "direct_book_exchange": (venue_proof.bid_exchange
                                             if venue_proof.verified else None),
                    "exchange_mapping_verified": exchange_map_verified,
                    "book_venue_proof_observed": venue_proof.verified,
                    "market_phase": ("CONTINUOUS" if not_halted is True
                                     else "UNKNOWN_OR_HALTED"),
                }
                mapping = ({exchange_code: "XSTO"} if exchange_map_verified
                           else {})
                snapshot = build_ibkr_tws_snapshot(
                    {"conId": conid, "isin": isin, "symbol": symbol,
                     "listing_mic": "XSTO", "currency": "SEK"},
                    trade, book, session, received_at=_iso(),
                    confirmed_exchange_map=mapping
                )
                gate = evaluate_primary_live_quote(
                    snapshot, instrument, now=_iso()
                )
                info["live_primary_quote_verified"] = gate.accepted_as_primary_live
                info["reasons"] = list(gate.reasons)
                if gate.accepted_as_primary_live:
                    # Never expose entitlement tokens or full quote payloads.
                    info["quote_age_status"] = "provider_live_xsto"
                    if analyst_result is not None:
                        preview = build_live_alert(
                            {"isin": isin, "symbol": symbol, "mic": "XSTO"},
                            analyst_result, gate, now=_iso(),
                            capital_sek=capital_sek
                        )
                        info["stock_analyst_preview"] = preview
        return info
    finally:
        if client.subscription_started:
            for ticker_id in (601,):
                client.cancelMktData(ticker_id)
            for ticker_id in ((602, 603) if client.book_subscription_started else (602,)):
                client.cancelTickByTickData(ticker_id)
        client.disconnect()
        thread.join(timeout=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--conid", type=int, required=True)
    parser.add_argument("--isin", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--exchange-code", required=True,
                        help="Exact IBKR primary venue code; do not guess")
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--client-id", type=int, default=77)
    parser.add_argument("--duration", type=int, default=50)
    parser.add_argument("--analysis-file", type=Path, default=None,
                        help="Optional local Stock Analyst technical JSON; dry-run only")
    parser.add_argument("--capital-sek", type=int, default=15000)
    parser.add_argument("--confirm-exchange-map", action="store_true",
                        help="Only when independently validated against IBKR primary venue")
    parser.add_argument("--confirm-bot-analytics-rights", action="store_true",
                        help="Only after reading IBKR/Nasdaq data usage entitlements")
    parser.add_argument("--confirm-live-entitlement", action="store_true",
                        help="Only after confirmed active Nordic Equity L1 subscription")
    args = parser.parse_args()
    analysis = None
    if args.analysis_file is not None:
        analysis = json.loads(args.analysis_file.read_text(encoding="utf-8"))
        if not isinstance(analysis, dict):
            parser.error("--analysis-file must contain one Stock Analyst JSON object")
    report = run_local_probe(
        conid=args.conid, isin=args.isin, symbol=args.symbol,
        exchange_code=args.exchange_code, port=args.port,
        client_id=args.client_id, duration_seconds=args.duration,
        exchange_map_verified=args.confirm_exchange_map,
        bot_rights_confirmed=args.confirm_bot_analytics_rights,
        live_entitlement_confirmed=args.confirm_live_entitlement,
        analyst_result=analysis, capital_sek=args.capital_sek
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
