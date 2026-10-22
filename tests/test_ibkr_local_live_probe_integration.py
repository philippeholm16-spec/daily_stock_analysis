"""Full localhost IBKR one-stock read-only callback *simulation*.

This does not contact IBKR and cannot verify real subscriptions. It verifies
the complete production callback, venue-proof, synchronized bid/ask,
entitlement, cleanup, and zero-order plumbing using a deterministic fake TWS.
"""
from datetime import datetime, timedelta, timezone
from types import ModuleType, SimpleNamespace
import sys

from scripts import ibkr_local_live_probe


NOW = datetime(2026, 10, 22, 7, 30, tzinfo=timezone.utc)
ISIN = "SE0000115446"


def install_ibkr_fake(monkeypatch, *, delayed=False, trade_exchange="SFB",
                      wrong_isin=False):
    events = []
    clock = SimpleNamespace(value=0.0)

    class FakeThread:
        def __init__(self, target, daemon=False):
            self.target = target
        def start(self):
            self.target()
        def join(self, timeout=None):
            pass

    class EWrapper:
        pass

    class EClient:
        def __init__(self, wrapper):
            self.connected = False

        def connect(self, host, port, clientId):
            events.append(("connect", host, port, clientId))
            self.connected = True

        def isConnected(self):
            return self.connected

        def run(self):
            self.nextValidId(1)

        def reqContractDetails(self, req_id, contract):
            events.append(("reqContractDetails", contract.conId))
            details = SimpleNamespace(
                contract=SimpleNamespace(
                    conId=contract.conId, symbol="VOLV", secType="STK",
                    currency="SEK", localSymbol="VOLV B", primaryExchange="SFB"
                ),
                secIdList=[SimpleNamespace(
                    key="ISIN", value="SE0021628898" if wrong_isin else ISIN
                )]
            )
            self.contractDetails(req_id, details)
            self.contractDetailsEnd(req_id)

        def reqMarketDataType(self, data_type):
            events.append(("reqMarketDataType", data_type))

        def reqMktData(self, ticker, contract, generic, snapshot, regSnap, options):
            events.append(("reqMktData", ticker))
            self.marketDataType(ticker, 3 if delayed else 1)
            self.tickReqParams(ticker, 0.01, "a6", 1)
            self.tickPrice(ticker, 1, 100.0, None)
            self.tickPrice(ticker, 2, 100.05, None)
            self.tickString(ticker, 32, "A")
            self.tickString(ticker, 33, "A")
            self.tickGeneric(ticker, 49, 0)

        def reqSmartComponents(self, req_id, mapping_code):
            events.append(("reqSmartComponents", mapping_code))
            self.smartComponents(req_id, [
                SimpleNamespace(exchangeLetter="A", exchange="SFB")
            ])

        def reqTickByTickData(self, ticker, contract, tick_type, count, ignore_size):
            events.append(("reqTickByTickData", tick_type))
            if tick_type == "Last":
                self.tickByTickAllLast(ticker, 1, int((NOW - timedelta(
                    seconds=3)).timestamp()), 100.0, 1000, None,
                    trade_exchange, "")
            elif tick_type == "BidAsk":
                self.tickPrice(601, 1, 100.0, None)
                self.tickPrice(601, 2, 100.05, None)
                self.tickString(601, 32, "A")
                self.tickString(601, 33, "A")
                self.tickByTickBidAsk(
                    ticker, int((NOW-timedelta(seconds=2)).timestamp()),
                    100.0, 100.05, 50, 50, None
                )

        def cancelMktData(self, ticker):
            events.append(("cancelMktData", ticker))

        def cancelTickByTickData(self, ticker):
            events.append(("cancelTickByTickData", ticker))

        def disconnect(self):
            events.append(("disconnect",))
            self.connected = False

        def placeOrder(self, *args):
            raise AssertionError("absolutely no IBKR trading API")

    class Contract:
        pass

    for name, attrs in (
        ("ibapi", {}),
        ("ibapi.client", {"EClient": EClient}),
        ("ibapi.wrapper", {"EWrapper": EWrapper}),
        ("ibapi.contract", {"Contract": Contract}),
    ):
        module = ModuleType(name)
        for attr, value in attrs.items():
            setattr(module, attr, value)
        monkeypatch.setitem(sys.modules, name, module)

    monkeypatch.setattr(ibkr_local_live_probe.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        ibkr_local_live_probe.time, "monotonic", lambda: clock.value
    )
    def sleep(seconds):
        clock.value += seconds
    monkeypatch.setattr(ibkr_local_live_probe.time, "sleep", sleep)
    monkeypatch.setattr(ibkr_local_live_probe, "_iso", lambda: NOW)
    return events


def execute(**kwargs):
    return ibkr_local_live_probe.run_local_probe(
        conid=1111, isin=ISIN, symbol="VOLV B", exchange_code="SFB",
        port=7497, duration_seconds=50,
        exchange_map_verified=True, bot_rights_confirmed=True,
        live_entitlement_confirmed=True, **kwargs
    )


def test_full_one_stock_primary_live_simulation(monkeypatch):
    events = install_ibkr_fake(monkeypatch)
    report = execute()
    assert report["live_primary_quote_verified"]
    assert report["bid_and_ask_primary_venue_observed"]
    assert report["primary_book_prices_agree"]
    assert report["upstream_isin_confirmed"]
    assert ("reqSmartComponents", "a6") in events
    assert ("reqTickByTickData", "BidAsk") in events
    assert events[-1] == ("disconnect",)
    assert not [x for x in events if x[0] == "placeOrder"]


def test_fake_delayed_nordic_quote_cannot_pass(monkeypatch):
    install_ibkr_fake(monkeypatch, delayed=True)
    report = execute()
    assert not report["live_primary_quote_verified"]
    assert "unapproved_provider_or_non_live_data_type" in report["reasons"]


def test_fake_cboe_trade_venue_cannot_pass(monkeypatch):
    install_ibkr_fake(monkeypatch, trade_exchange="CBOE")
    report = execute()
    assert not report["live_primary_quote_verified"]
    assert "nonprimary_or_unverified_venue" in report["reasons"]


def test_wrong_contract_isin_cannot_pass(monkeypatch):
    install_ibkr_fake(monkeypatch, wrong_isin=True)
    report = execute()
    assert not report["live_primary_quote_verified"]
    assert "exchange_contract_isin_not_proven" in report["reasons"]
