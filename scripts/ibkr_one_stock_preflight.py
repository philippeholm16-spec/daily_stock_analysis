"""Local Mac preflight for IBKR one-stock real-time test.

Zero credentials or broker API calls. Checks only whether a TWS/Gateway
listener is available on the user's own loopback interface and whether the
official ibapi Python package is installed. It cannot validate permissions
or infer that quotes are live.
"""
import argparse
import importlib.util
import json
import platform
import socket
import sys


IBKR_PORTS = (7496, 7497, 4001, 4002)


def preflight(*, port=7497, package_available=None, connect_test=None):
    if isinstance(port, bool) or not isinstance(port, int) or port not in IBKR_PORTS:
        raise ValueError("unsupported_ibkr_loopback_port")
    if package_available is None:
        package_available = importlib.util.find_spec("ibapi") is not None
    if connect_test is None:
        def connect_test():
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
    try:
        listening = bool(connect_test())
    except (OSError, TimeoutError):
        listening = False
    missing = []
    if not package_available:
        missing.append("ibapi_python_package_not_installed")
    if not listening:
        missing.append("tws_or_gateway_local_socket_not_reachable")
    return {
        "mode": "LOCAL_READ_ONLY_PREFLIGHT",
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "machine_os": platform.system(),
        "target_host": "127.0.0.1",
        "target_port": port,
        "ibapi_installed": package_available,
        "loopback_socket_reachable": listening,
        "ready_for_isin_lookup": not missing,
        "issues": missing,
        "nasdaq_live_entitlement_verified": False,
        "verified_stockholm_quote_observed": False,
        "broker_orders_enabled": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=7497)
    args = parser.parse_args()
    result = preflight(port=args.port)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ready_for_isin_lookup"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
