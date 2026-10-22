"""Credential-free Mac readiness checks cannot imply a live quote."""
import pytest

from scripts.ibkr_one_stock_preflight import preflight


def test_warm_local_gateway_and_ibapi_only_ready_for_lookup():
    report = preflight(
        port=7497, package_available=True, connect_test=lambda: True
    )
    assert report["ready_for_isin_lookup"]
    assert not report["verified_stockholm_quote_observed"]
    assert not report["nasdaq_live_entitlement_verified"]
    assert report["broker_orders_enabled"] is False


def test_no_ibkr_listener_reports_next_step():
    def refuse():
        raise ConnectionRefusedError
    result = preflight(port=7497, package_available=True, connect_test=refuse)
    assert "tws_or_gateway_local_socket_not_reachable" in result["issues"]
    assert not result["ready_for_isin_lookup"]


def test_missing_ibapi_reported_explicitly():
    result = preflight(port=7497, package_available=False,
                       connect_test=lambda: True)
    assert result["issues"] == ["ibapi_python_package_not_installed"]
    assert not result["ready_for_isin_lookup"]


def test_nonstandard_or_public_port_rejected():
    with pytest.raises(ValueError, match="unsupported"):
        preflight(port=9999, package_available=True, connect_test=lambda: True)
