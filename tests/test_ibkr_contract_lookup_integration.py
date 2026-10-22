"""Exercise complete one-stock ISIN lookup callback flow without IBKR login.

The fake TWS server validates that the production client asks for EXACTLY
one Swedish stock ContractDetails using secIdType=ISIN, never places orders,
and refuses unsupported/ambiguous results.
"""
from types import ModuleType, SimpleNamespace
import sys

from scripts.ibkr_contract_lookup import lookup_local


ISIN = "SE0000115446"


def modules(monkeypatch, *, return_matches=1, returned_isin=ISIN):
    calls = []

    class EWrapper:
        pass

    class EClient:
        def __init__(self, wrapper):
            self.connected = False

        def connect(self, host, port, clientId):
            calls.append(("connect", host, port, clientId))
            self.connected = True

        def isConnected(self):
            return self.connected

        def run(self):
            self.nextValidId(999)

        def reqContractDetails(self, request_id, contract):
            calls.append(("reqContractDetails", request_id, contract.secIdType,
                          contract.secId, contract.exchange,
                          contract.currency, contract.secType))
            for index in range(return_matches):
                detail = SimpleNamespace(
                    contract=SimpleNamespace(
                        conId=4711+index, symbol="VOLV", localSymbol="VOLV B",
                        secType="STK", currency="SEK", primaryExchange="SFB"
                    ),
                    secIdList=[
                        SimpleNamespace(key="ISIN", value=returned_isin)
                    ]
                )
                self.contractDetails(request_id, detail)
            self.contractDetailsEnd(request_id)

        def disconnect(self):
            calls.append(("disconnect",))
            self.connected = False

        def placeOrder(self, *args):
            raise AssertionError("The contract lookup must never place orders")

    class Contract:
        pass

    ibapi = ModuleType("ibapi")
    client = ModuleType("ibapi.client")
    wrapper = ModuleType("ibapi.wrapper")
    contract = ModuleType("ibapi.contract")
    client.EClient, wrapper.EWrapper, contract.Contract = EClient, EWrapper, Contract
    for module in (ibapi, client, wrapper, contract):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    return calls


def test_local_ibkr_resolver_uses_only_readonly_isin_contract_query(monkeypatch):
    calls = modules(monkeypatch)
    output = lookup_local(isin=ISIN, port=7497)
    assert output["status"] == "ISIN_VERIFIED"
    assert output["instrument"]["conid"] == 4711
    assert calls[0][:3] == ("connect", "127.0.0.1", 7497)
    assert calls[1] == ("reqContractDetails", 501, "ISIN", ISIN,
                        "SMART", "SEK", "STK")
    assert calls[-1] == ("disconnect",)


def test_lookup_rejects_multiple_conids_without_guessing(monkeypatch):
    modules(monkeypatch, return_matches=2)
    output = lookup_local(isin=ISIN)
    assert output["status"] == "ISIN_UNVERIFIED"
    assert output["reason"] == "multiple_matching_share_contracts"


def test_lookup_rejects_missing_or_mismatched_isin(monkeypatch):
    modules(monkeypatch, returned_isin="SE0021628898")
    output = lookup_local(isin=ISIN)
    assert output["status"] == "ISIN_UNVERIFIED"


def test_lookup_unavailable_gateway_report(monkeypatch):
    calls = modules(monkeypatch)
    # A fake failed login should not produce contract lookup success.
    # This validates the production path's own error classification.
    def fail(self, host, port, clientId):
        calls.append(("refused", host, port))
        self.connected = False
    monkeypatch.setattr(sys.modules["ibapi.client"].EClient, "connect", fail)
    output = lookup_local(isin=ISIN)
    assert output["status"] == "LOCAL_GATEWAY_NOT_AVAILABLE"
    assert output["no_orders"] is True
