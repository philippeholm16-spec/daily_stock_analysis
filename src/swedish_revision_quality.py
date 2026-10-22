"""Independent sourced revision-diligence gate for Swedish equity research.

Crucial separation:
- An analyst's DCF 'fair value' is NOT an investment bank's price target.
- Individual bank changes are NOT a consensus EPS revision history.
- A low target gap is NOT a predictive probability or executable order.

Do not publish a BUY verdict if earnings estimate momentum is not backed by
like-for-like, dated, independent consensus snapshots. No market API/orders.
"""
from datetime import datetime, timezone
from math import isfinite
from statistics import median
from urllib.parse import urlsplit

ALLOWED = {"price_target", "fair_value"}
KNOWN_CURRENCY = "SEK"


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("missing_time")
    try:
        if len(value) == 10 and value[4] == "-" and value[7] == "-":
            # Published articles frequently provide dates, not times.
            # Interpret date as midnight UTC for age checks only; never
            # present that as an observed intraday publication timestamp.
            ts = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        else:
            ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                raise ValueError("timezone_required")
    except ValueError as exc:
        raise ValueError("invalid_time") from exc
    return ts.astimezone(timezone.utc)


def _source(url):
    return isinstance(url, str) and urlsplit(url).scheme == "https" and bool(urlsplit(url).netloc)


def _positive(value):
    return (isinstance(value, (float, int)) and not isinstance(value, bool)
            and isfinite(value) and value > 0)


def inspect_analyst_revisions(
    records, *, isin, now=None, short_interest=None,
    earnings_consensus_snapshots=None, max_revision_age_days=120
):
    """Return evidence and the risks WITHOUT granting a buy recommendation.

    Rows: house, kind, previous, current, effective_at, source, currency,
    horizon_months. Latest per house+kind; transparent counts not cherry-picked.
    Short data requires FI-sourced percentage and timestamp.
    EPS consensus snapshots: a pair of comparable, timestamped
    {"as_of", "fiscal_year", "currency", "eps_basis",
     "eps", "analyst_count", "source"} records.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now_timezone_required")
    if not isinstance(isin, str) or len(isin) != 12 or not isin[:2].isalpha():
        raise ValueError("exact_isin_required")
    if not isinstance(records, list):
        raise ValueError("records_must_be_list")
    latest = {}
    rejected = []
    for i, row in enumerate(records):
        if not isinstance(row, dict) or row.get("isin") != isin:
            rejected.append({"index": i, "reason": "identity_mismatch"})
            continue
        kind, house = row.get("kind"), row.get("house")
        if kind not in ALLOWED or not isinstance(house, str) or not house.strip():
            rejected.append({"index": i, "reason": "kind_or_house_missing"})
            continue
        previous, current = row.get("previous"), row.get("current")
        if (not _positive(previous) or not _positive(current)
                or row.get("currency") != KNOWN_CURRENCY
                or not _source(row.get("source"))
                or (kind == "price_target" and row.get("horizon_months") != 12)):
            rejected.append({"index": i, "reason": "noncomparable_or_uncited_revision"})
            continue
        try:
            ts = _timestamp(row.get("effective_at"))
        except ValueError:
            rejected.append({"index": i, "reason": "invalid_publication_time"})
            continue
        age = (now - ts).total_seconds()
        if age < -120 or age > max_revision_age_days * 86400:
            rejected.append({"index": i, "reason": "revision_outside_review_window"})
            continue
        key = (kind, house.casefold().strip())
        if key not in latest or ts > latest[key][0]:
            latest[key] = (ts, row)
    separated = {}
    for kind in ALLOWED:
        relevant = sorted(
            (row for (typ, _), (ts, row) in latest.items() if typ == kind),
            key=lambda row: row["house"].casefold()
        )
        changes = [100 * (row["current"] / row["previous"] - 1)
                   for row in relevant]
        separated[kind] = {
            "count": len(relevant),
            "raised": sum(x > .000001 for x in changes),
            "lowered": sum(x < -.000001 for x in changes),
            "unchanged": sum(abs(x) <= .000001 for x in changes),
            "median_pct_change": round(median(changes), 2) if changes else None,
            "changes": [
                {
                    "house": row["house"],
                    "old": row["previous"],
                    "new": row["current"],
                    "change_pct": round(100*(row["current"]/row["previous"]-1), 2),
                    "effective_at": row["effective_at"],
                    "source": row["source"],
                } for row in relevant
            ],
        }
    short_info = {
        "verified": False, "percentage": None, "high_short_risk": None,
        "reason": "missing_fresh_fi_short_interest",
    }
    if isinstance(short_interest, dict):
        pct = short_interest.get("pct")
        try:
            at = _timestamp(short_interest.get("as_of"))
            age = (now - at).total_seconds()
            if (isinstance(pct, (int, float)) and not isinstance(pct, bool)
                    and isfinite(pct) and 0 <= pct <= 100
                    and _source(short_interest.get("source"))
                    and 0 <= age <= 7 * 86400):
                short_info = {
                    "verified": True,
                    "percentage": float(pct),
                    "high_short_risk": pct >= 10,
                    "reason": "fresh_fi_reported_aggregate_short_interest",
                }
        except ValueError:
            pass
    eps_info = {
        "verified": False,
        "change_pct": None,
        "direction": "UNKNOWN",
        "reason": "no_comparable_two_date_consensus_earnings_estimates",
    }
    if (isinstance(earnings_consensus_snapshots, list)
            and len(earnings_consensus_snapshots) == 2):
        try:
            before, after = sorted(earnings_consensus_snapshots,
                                   key=lambda row: _timestamp(row["as_of"]))
            older, newer = _timestamp(before["as_of"]), _timestamp(after["as_of"])
            fields = ("fiscal_year", "eps_basis", "currency")
            same_basis = all(before.get(f) == after.get(f) for f in fields)
            if (same_basis and before.get("currency") == KNOWN_CURRENCY
                    and before.get("eps_basis") in ("REPORTED", "ADJUSTED")
                    and _positive(before.get("eps")) and _positive(after.get("eps"))
                    and all(isinstance(r.get("analyst_count"), int)
                            and r["analyst_count"] >= 3 for r in (before, after))
                    and all(_source(r.get("source")) for r in (before, after))
                    and 0 < (newer-older).total_seconds() <= 100*86400
                    and 0 <= (now-newer).total_seconds() <= 30*86400):
                change = 100*(after["eps"]/before["eps"] - 1)
                eps_info = {
                    "verified": True,
                    "change_pct": round(change, 2),
                    "direction": ("UP" if change > 0.1
                                  else "DOWN" if change < -0.1 else "FLAT"),
                    "reason": "same_fiscal_period_eps_consensus_compared",
                    "analysts_newer": after["analyst_count"],
                    "fiscal_year": after["fiscal_year"],
                }
        except (ValueError, TypeError, KeyError, OverflowError):
            pass

    diligence_ready = (
        separated["price_target"]["count"] >= 4
        and short_info["verified"] and eps_info["verified"]
    )
    warnings = []
    if not diligence_ready:
        warnings.append("critical_data_missing_no_buy_verdict")
    if short_info["high_short_risk"] is True:
        warnings.append("high_reported_short_interest")
    if eps_info["direction"] == "DOWN":
        warnings.append("negative_consensus_eps_momentum")
    if separated["price_target"]["lowered"] > separated["price_target"]["raised"]:
        warnings.append("more_target_cuts_than_raises_in_observed_sample")
    return {
        "isin": isin,
        "data_gate": ("DILIGENCE_DATA_COMPLETE_FOR_REVIEW"
                      if diligence_ready else "RESEARCH_ONLY_CRITICAL_DATA_MISSING"),
        "price_target_revisions": separated["price_target"],
        "fair_value_revisions": separated["fair_value"],
        "short_interest": short_info,
        "earnings_consensus_momentum": eps_info,
        "rejected_records": rejected,
        "warnings": warnings,
        "not_exhaustive_analyst_universe": True,
        "not_a_probability": True,
        "actionable": False,
        "trading_signal": None,
    }
