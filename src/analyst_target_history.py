"""Auditable 30/90/180-day target-momentum histories for exact listed shares.

Disambiguates an analyst firm from a stock with a similar name. A raise on
Elekta by Pareto Securities may coexist with a negative 180-day path;
DNB Carnegie's cut to Pareto BANK can never count as an Elekta revision.

This is research evidence, not a calibrated prediction or trading signal.
"""
from datetime import datetime, timezone
from math import isfinite
from urllib.parse import urlsplit

VALID_MICS = {"XSTO", "XOSL"}


def _date(x):
    if not isinstance(x, str):
        raise ValueError("missing_observation_date")
    try:
        result = datetime.fromisoformat(x.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_observation_date") from exc
    if result.tzinfo is None:
        raise ValueError("observation_timezone_required")
    return result.astimezone(timezone.utc)


def _positive(x):
    return (isinstance(x, (float, int)) and not isinstance(x, bool)
            and isfinite(x) and x > 0)


def _source(uri):
    if not isinstance(uri, str):
        return False
    parsed = urlsplit(uri)
    return parsed.scheme == "https" and bool(parsed.netloc)


def inspect_target_path(events, *, isin, mic, symbol, issuer, currency,
                        now=None, windows=(30, 90, 180)):
    """Return same-house chronological net change for each observation window.

    Each observation needs the published analyst target *before* and *after*
    the change. A window's baseline is the old target of the earliest
    in-window event, not the oldest available target in another window.
    This is not equivalent to changes in EPS consensus estimates.
    """
    now = now or datetime.now(timezone.utc)
    as_of = _date(now.isoformat())
    if (not isinstance(isin, str) or len(isin) != 12
            or mic not in VALID_MICS
            or not isinstance(symbol, str) or not symbol.strip()
            or not isinstance(issuer, str) or not issuer.strip()
            or currency not in ("SEK", "NOK")
            or not isinstance(events, list)
            or not isinstance(windows, tuple)
            or any(not isinstance(n, int) or isinstance(n, bool) or n < 1 or n > 365 for n in windows)):
        raise ValueError("invalid_listed_share_or_window")
    rows = []
    for item in events:
        if not isinstance(item, dict):
            raise ValueError("malformed_target_revision")
        if any(item.get(k) != v for k, v in (
            ("isin", isin), ("mic", mic), ("symbol", symbol),
            ("issuer", issuer), ("currency", currency)
        )):
            raise ValueError("different_stock_broker_or_currency_mixed")
        if item.get("kind") != "BROKER_TARGET":
            raise ValueError("fair_value_or_other_model_is_not_broker_target")
        if (not _positive(item.get("old")) or not _positive(item.get("new"))
                or not _source(item.get("source"))):
            raise ValueError("unverified_target_revision")
        day = _date(item.get("at"))
        age = (as_of-day).total_seconds()
        if age < -120 or age > 365 * 86400:
            raise ValueError("target_outside_available_history")
        rows.append((day, item))
    rows.sort(key=lambda x: x[0])
    for i in range(1, len(rows)):
        earlier, later = rows[i-1], rows[i]
        if earlier[0] == later[0]:
            raise ValueError("duplicate_broker_revision_same_timestamp")
        if abs(earlier[1]["new"] - later[1]["old"]) > 0.000001:
            raise ValueError("inconsistent_broker_target_chain")
    output = {}
    for n in windows:
        selected = [r for stamp, r in rows
                    if 0 <= (as_of-stamp).total_seconds() <= n * 86400]
        if not selected:
            output[str(n)] = {"direction": "NO_OBSERVED_CHANGE",
                              "change_pct": None, "observations": 0}
            continue
        first, last = selected[0]["old"], selected[-1]["new"]
        pct = round(100*(last/first-1), 2)
        output[str(n)] = {
            "direction": ("UP" if pct > .1 else "DOWN" if pct < -.1 else "FLAT"),
            "change_pct": pct, "observations": len(selected),
            "from_target": first, "to_target": last,
        }
    latest = rows[-1][1] if rows else None
    return {
        "identity": {"isin": isin, "mic": mic, "symbol": symbol,
                     "analyst_house": issuer, "currency": currency},
        "latest_revision": (
            {"old": latest["old"], "new": latest["new"],
             "change_pct": round(100*(latest["new"]/latest["old"]-1), 2),
             "as_of": latest["at"], "source": latest["source"]}
            if latest else None
        ),
        "time_windows_days": output,
        "eps_consensus_momentum": "NOT_DERIVED_FROM_TARGET_CHANGES",
        "all_analysts_covered": False,
        "actionable": False,
        "trade_signal": None,
    }
