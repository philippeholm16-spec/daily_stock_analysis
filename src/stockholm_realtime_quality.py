"""Fail-closed *primary Nasdaq Stockholm* live quote validation.

Designed for authorized IBKR Nordic Equity L1 streaming data. No network,
accounts, orders or automatic license claims. The upstream IBKR TWS collector
must verify contract conId/ISIN and resolve trade + bid/ask exchange to XSTO
using contract detail and the documented exchange mapping.

Cboe Europe live quotes, Avanza 'isRealTime: false', stale timestamps, and
IBKR delayed/frozen callbacks are all RESEARCH_ONLY.

Live eligibility verifies quote recency, not historical bar completeness,
market-wide coverage, strategy accuracy, rights of redistribution, or fills.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
import re
from zoneinfo import ZoneInfo

ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")


@dataclass(frozen=True)
class QuoteGateResult:
    accepted_as_primary_live: bool
    reasons: tuple[str, ...]
    quote: dict | None = None

    def as_dict(self):
        return {"accepted_as_primary_live": self.accepted_as_primary_live,
                "reasons": list(self.reasons), "quote": self.quote}


def _time(raw):
    """Only timezone-aware ISO 8601 timestamps; no guessing from receipt time."""
    if not isinstance(raw, str):
        return None
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except ValueError:
        return None


def _money(raw):
    return (isinstance(raw, (float, int)) and not isinstance(raw, bool)
            and isfinite(raw) and raw > 0)


def _age_reason(label, stamp, *, now, max_age):
    if stamp is None:
        return label + "_timestamp_missing"
    diff = (now - stamp).total_seconds()
    if diff < -2:
        return label + "_future_timestamp"
    if diff > max_age:
        return label + "_stale"
    return None


def evaluate_primary_live_quote(snapshot, instrument, *, now=None,
                                max_trade_age_seconds=60,
                                max_book_age_seconds=15,
                                max_transport_lag_seconds=10,
                                max_spread_pct=0.5):
    """Check one *independently identified* XSTO contract and its real-time tick.

    Snapshot format expected from a licensed collector:
      provider = IBKR_TWS_API
      market_data_type = 1 (IBKR 1=live, 3=delayed)
      entitlement_confirmed = True (collector confirms active subscription)
      rights_confirmed = True (operator confirms permitted internal use)
      session_authenticated = True
      contract_id = integer matching a verified ISIN/conId mapping
      symbol, isin, listing_mic = matching XSTO identity
      trade_venue_mic = XSTO, book_venue_mic = XSTO
      trade_ts_utc, bid_ask_ts_utc, received_at_utc = ISO UTC
      last, bid, ask > 0
      market_phase = CONTINUOUS

    Returns verified quote FOR FURTHER RESEARCH. In particular, does not
    mark a trading strategy actionable; regulatory and strategy gates remain.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("naive_now")
    if not isinstance(snapshot, dict) or not isinstance(instrument, dict):
        return QuoteGateResult(False, ("missing_snapshot_or_instrument",))
    reasons = []
    if (snapshot.get("provider") != "IBKR_TWS_API"
            or snapshot.get("market_data_type") != 1
            or isinstance(snapshot.get("market_data_type"), bool)):
        reasons.append("unapproved_provider_or_non_live_data_type")
    if (snapshot.get("session_authenticated") is not True
            or snapshot.get("entitlement_confirmed") is not True
            or snapshot.get("rights_confirmed") is not True):
        reasons.append("subscription_or_usage_rights_not_confirmed")
    cid = instrument.get("contract_id")
    if (not isinstance(cid, int) or isinstance(cid, bool) or cid <= 0
            or snapshot.get("contract_id") != cid
            or not isinstance(instrument.get("isin"), str)
            or not ISIN_PATTERN.fullmatch(instrument["isin"])
            or not instrument.get("symbol")
            or instrument.get("listing_mic") != "XSTO"
            or snapshot.get("isin") != instrument.get("isin")
            or snapshot.get("symbol") != instrument.get("symbol")
            or snapshot.get("listing_mic") != "XSTO"
            or snapshot.get("currency") != "SEK"):
        reasons.append("xsto_share_class_or_contract_mismatch")
    if (snapshot.get("trade_venue_mic") != "XSTO"
            or snapshot.get("book_venue_mic") != "XSTO"
            or snapshot.get("exchange_mapping_confirmed") is not True):
        reasons.append("nonprimary_or_unverified_venue")
    if snapshot.get("market_phase") != "CONTINUOUS":
        reasons.append("not_continuous_trading")
    # Clock guard is not a complete holiday calendar. Open/halts must also be
    # independently indicated by the market-data provider.
    local_now = now.astimezone(ZoneInfo("Europe/Stockholm"))
    if (local_now.weekday() >= 5 or not
            ((local_now.hour == 9 and local_now.minute >= 0)
             or 10 <= local_now.hour < 17
             or (local_now.hour == 17 and local_now.minute < 25))):
        reasons.append("outside_regular_stockholm_session")
    last, bid, ask = (snapshot.get(k) for k in ("last", "bid", "ask"))
    if not all(_money(p) for p in (last, bid, ask)):
        reasons.append("missing_or_invalid_last_bid_ask")
    elif bid >= ask:
        reasons.append("crossed_or_locked_book")
    else:
        spread = (ask-bid)/((ask+bid)/2)*100
        if spread > max_spread_pct:
            reasons.append("spread_above_limit")
        if not (bid * 0.90 <= last <= ask * 1.10):
            reasons.append("last_quote_incoherent_with_book")
    stamps = {
        key: _time(snapshot.get(key))
        for key in ("trade_ts_utc", "bid_ask_ts_utc", "received_at_utc")
    }
    for key, limit in [
        ("trade_ts_utc", max_trade_age_seconds),
        ("bid_ask_ts_utc", max_book_age_seconds),
        ("received_at_utc", max_transport_lag_seconds),
    ]:
        name = key.split("_ts")[0].replace("_at_utc", "")
        issue = _age_reason(name, stamps[key], now=now, max_age=limit)
        if issue:
            reasons.append(issue)
    if stamps["trade_ts_utc"] and stamps["received_at_utc"]:
        lag = (stamps["received_at_utc"]-stamps["trade_ts_utc"]).total_seconds()
        if lag < -2 or lag > max_trade_age_seconds:
            reasons.append("trade_transport_or_clock_anomaly")
    if reasons:
        return QuoteGateResult(False, tuple(dict.fromkeys(reasons)))
    return QuoteGateResult(True, (), {
        "source": "IBKR_TWS_API",
        "last_price": float(last),
        "bid": float(bid),
        "ask": float(ask),
        "spread_pct": round((ask-bid)/((ask+bid)/2)*100, 4),
        "as_of": stamps["trade_ts_utc"].isoformat(),
        "bid_ask_as_of": stamps["bid_ask_ts_utc"].isoformat(),
        "listing_mic": "XSTO",
        "trade_venue_mic": "XSTO",
        "market_data_type": 1,
        "contract_id": cid,
        "isin": instrument["isin"],
        "symbol": instrument["symbol"],
        "data_quality": "PRIMARY_XSTO_LIVE_QUOTE_VERIFIED",
        "trade_signal": None,
        "actionable": False,
    })
