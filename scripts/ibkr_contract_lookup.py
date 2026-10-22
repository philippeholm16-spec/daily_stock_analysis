"""Discover exact IBKR contract ID from an ISIN via localhost TWS/Gateway.

A single read-only reqContractDetails request using Contract.secIdType='ISIN'
and secId=<ISIN> on SMART, as supported by official IBKR TWS documentation.

This is step ONE. It DOES NOT request quotes, prove Nasdaq Nordic market-data
entitlements, initiate subscriptions, send Telegram, or place orders.

CLI (on user's Mac after TWS API read-only enabled):
    python -m scripts.ibkr_contract_lookup --isin SE0000115446 --port 7497

The response exposes only security identity metadata, no account numbers.
"""
import argparse
import json
import re
import threading
from typing import Any

from src.ibkr_contract_identity import verify_contract_details

ISIN_REGEX = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")


def _field(value, key):
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def resolve_unique_contract(details, *, isin):
    """Pure security resolver: one unique conId independently confirmed by ISIN.

    Multiple ContractDetails results with the SAME conId are harmless; two
    distinct conIds matching the same ISIN need human/exchange review.
    """
    matches = {}
    for row in details:
        result = verify_contract_details(row, expected_isin=isin)
        if result is None:
            continue
        matches[result["conid"]] = result
    if len(matches) == 1:
        return {"resolved": True, "reason": "verified_single_conid",
                "instrument": next(iter(matches.values()))}
    return {"resolved": False,
            "reason": ("multiple_matching_share_contracts" if len(matches) > 1
                       else "contract_isin_not_verifiable"),
            "instrument": None, "matching_contract_count": len(matches)}


def lookup_local(*, isin, port=7497, client_id=78, timeout_seconds=25):
    """Read-only one-stock contract lookup on 127.0.0.1, never remote host."""
    if (not isinstance(isin, str) or not ISIN_REGEX.fullmatch(isin)
            or port not in (7496, 7497, 4001, 4002)
            or not isinstance(client_id, int) or isinstance(client_id, bool)
            or client_id < 1 or not 5 <= timeout_seconds <= 60):
        raise ValueError("invalid_local_ibkr_lookup_parameters")
    try:
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper
        from ibapi.contract import Contract
    except ImportError as exc:
        raise RuntimeError("ibapi_not_installed_on_mac") from exc

    contract = Contract()
    contract.secIdType = "ISIN"
    contract.secId = isin
    contract.secType = "STK"
    contract.currency = "SEK"
    contract.exchange = "SMART"

    class Reader(EWrapper, EClient):
        def __init__(self):
            EClient.__init__(self, self)
            self.done = threading.Event()
            self.matches = []
            self.errors = []
            self.queried = False
            self.lock = threading.Lock()

        def nextValidId(self, orderId):
            self.queried = True
            self.reqContractDetails(501, contract)

        def contractDetails(self, reqId, details):
            if reqId == 501:
                with self.lock:
                    if len(self.matches) < 100:
                        self.matches.append(details)

        def contractDetailsEnd(self, reqId):
            if reqId == 501:
                self.done.set()

        def error(self, reqId, errorCode, errorString,
                  advancedOrderRejectJson=""):
            if errorCode not in (2104, 2106, 2158):
                with self.lock:
                    self.errors.append(int(errorCode))

    client = Reader()
    thread = None
    try:
        client.connect("127.0.0.1", port, client_id)
        if not client.isConnected():
            return {"status": "LOCAL_GATEWAY_NOT_AVAILABLE",
                    "resolved": False, "reason": "ibkr_connection_failed",
                    "no_orders": True}
        thread = threading.Thread(target=client.run, daemon=True)
        thread.start()
        finished = client.done.wait(timeout_seconds)
        with client.lock:
            matches = list(client.matches)
            error_codes = sorted(set(client.errors))
        if not finished:
            return {"status": "CONTRACT_LOOKUP_TIMEOUT", "resolved": False,
                    "reason": "ibkr_contract_details_end_not_received",
                    "ibkr_error_codes": error_codes, "no_orders": True}
        identity = resolve_unique_contract(matches, isin=isin)
        return {"status": "ISIN_VERIFIED" if identity["resolved"]
                else "ISIN_UNVERIFIED",
                "requested_isin": isin,
                "ibkr_error_codes": error_codes,
                "no_orders": True, **identity}
    finally:
        if client.isConnected():
            client.disconnect()
        if thread is not None:
            thread.join(timeout=2)


def main():
    parser = argparse.ArgumentParser(
        description="Resolve one Swedish stock ISIN to a verified local IBKR contract ID")
    parser.add_argument("--isin", required=True)
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--client-id", type=int, default=78)
    parser.add_argument("--timeout", type=int, default=25)
    args = parser.parse_args()
    try:
        result = lookup_local(isin=args.isin, port=args.port,
                              client_id=args.client_id, timeout_seconds=args.timeout)
    except (ValueError, RuntimeError, ConnectionError, OSError) as exc:
        result = {"status": "LOOKUP_NOT_COMPLETED",
                  "resolved": False, "reason": type(exc).__name__,
                  "no_orders": True}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("resolved"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
