"""Prevent IBKR one-stock data scripts from ever evolving into trading tools.

The TWS API client supports trading; our restricted diagnostic scripts must
NEVER call order-entry or private account-reading EClient endpoints.
"""
import ast
from pathlib import Path

import pytest


IBKR_LOCAL_SCRIPTS = (
    Path("scripts/ibkr_contract_lookup.py"),
    Path("scripts/ibkr_local_live_probe.py"),
    Path("scripts/ibkr_one_stock_preflight.py"),
)

FORBIDDEN = {
    "placeOrder", "cancelOrder", "reqPositions", "reqPositionsMulti",
    "reqAccountUpdates", "reqAccountSummary", "reqExecutions",
    "reqAllOpenOrders", "reqOpenOrders", "reqCompletedOrders",
    "reqPnL", "reqPnLSingle", "reqAccountUpdatesMulti",
    "reqManagedAccts", "reqFA",
}


@pytest.mark.parametrize("source_path", IBKR_LOCAL_SCRIPTS)
def test_local_ibkr_scripts_contain_no_order_or_account_api_calls(source_path):
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    attempted = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            name = (target.attr if isinstance(target, ast.Attribute)
                    else target.id if isinstance(target, ast.Name) else None)
            if name in FORBIDDEN:
                attempted.append(name)
    assert not attempted, f"local diagnostic unexpectedly uses account/trade API: {attempted}"
