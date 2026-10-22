"""Source-checked analyst target *revision* momentum, separate from fair value.

A broker 12-month target change is NOT a Morningstar multi-year DCF fair-value
revision. Never combine their magnitudes or currencies. Only same-broker
before/after targets can contribute to the 90-day breadth indicator.

This evaluates historical public reports; it does NOT supply market-data
licences, estimate an unobserved EPS consensus, or authorize a buy order.
"""
from datetime import datetime, timezone
from math import isfinite
from statistics import median
from urllib.parse import urlsplit


def _date(raw):
    if not isinstance(raw, str):
        raise ValueError("missing_evidence_date")
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("malformed_evidence_date") from exc
    if stamp.tzinfo is None:
        raise ValueError("timezone_required")
    return stamp.astimezone(timezone.utc)


def _positive(n):
    return (isinstance(n, (int, float)) and not isinstance(n, bool)
            and isfinite(n) and n > 0)


def _source(source):
    if not isinstance(source, str):
        return False
    url = urlsplit(source)
    return url.scheme == "https" and bool(url.netloc)


def _check_event(event, *, symbol, now, lookback_days=90):
    if (not isinstance(event, dict)
            or event.get("symbol") != symbol or event.get("mic") != "XSTO"):
        raise ValueError("wrong_security_or_exchange_for_revision")
    kind = event.get("kind")
    if kind not in ("BROKER_TARGET", "MODEL_FAIR_VALUE"):
        raise ValueError("unsupported_revision_kind")
    stamp = _date(event.get("as_of"))
    age = (now - stamp).total_seconds()
    if age < -120 or age > lookback_days * 86400:
        raise ValueError("revision_outside_lookback")
    issuer = event.get("issuer")
    if not isinstance(issuer, str) or len(issuer.strip()) < 3:
        raise ValueError("missing_revision_issuer")
    if not _source(event.get("source")):
        raise ValueError("missing_revision_source")
    old, new = event.get("old"), event.get("new")
    if not _positive(old) or not _positive(new):
        raise ValueError("invalid_revision_prices")
    currency = event.get("currency")
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
        raise ValueError("missing_target_currency")
    if kind == "BROKER_TARGET":
        # One firm gets one vote; never pretend a newsroom BUY rating means
        # the firm's price target increased.
        if issuer.strip().casefold() in ("morningstar fair value", "morningstar"):
            raise ValueError("valuation_model_cannot_be_broker_target")
    return {
        "symbol": symbol, "kind": kind, "issuer": issuer.strip(),
        "as_of": stamp.isoformat(), "old": float(old), "new": float(new),
        "currency": currency.upper(), "source": event["source"],
        "change_pct": 100.0 * (new / old - 1.0),
    }


def target_revision_momentum(events, *, symbol, now=None,
                             lookback_days=90, minimum_brokers=3):
    """Track recent broker revision breadth, with fair-value model separate.

    Includes the most recent observable revision per broker only so frequent
    houses cannot overwhelm independent houses. Missing coverage is UNKNOWN,
    never zero or a positive buy score.
    """
    now = now or datetime.now(timezone.utc)
    if not isinstance(events, list):
        raise ValueError("revisions_must_be_list")
    if not 1 <= minimum_brokers <= 30:
        raise ValueError("invalid_minimum_brokers")
    broker = {}
    fair = {}
    for raw in events:
        item = _check_event(raw, symbol=symbol, now=now, lookback_days=lookback_days)
        dest = broker if item["kind"] == "BROKER_TARGET" else fair
        key = item["issuer"].casefold()
        if key not in dest or dest[key]["as_of"] < item["as_of"]:
            dest[key] = item
    revisions = sorted(broker.values(), key=lambda x: (x["as_of"], x["issuer"]))
    valuations = sorted(fair.values(), key=lambda x: (x["as_of"], x["issuer"]))
    n = len(revisions)
    up = sum(x["change_pct"] > 0.01 for x in revisions)
    down = sum(x["change_pct"] < -0.01 for x in revisions)
    flat = n - up - down
    if n < minimum_brokers:
        signal = "UNKNOWN_INSUFFICIENT_BROKER_COVERAGE"
    elif up/n >= .65 and down/n <= .25:
        signal = "POSITIVE_BROKER_REVISION_BREADTH"
    elif down/n >= .65 and up/n <= .25:
        signal = "NEGATIVE_BROKER_REVISION_BREADTH"
    else:
        signal = "MIXED_BROKER_REVISION_BREADTH"
    return {
        "symbol": symbol,
        "observations": n,
        "positive_brokers": up, "negative_brokers": down,
        "flat_brokers": flat,
        "positive_share": round(up/n, 4) if n else None,
        "median_broker_change_pct": round(
            median(x["change_pct"] for x in revisions), 2
        ) if n else None,
        "momentum_label": signal,
        "broker_revisions": revisions,
        "fair_value_model_revisions": valuations,
        "fair_value_is_not_a_broker_consensus_target": True,
        "earnings_estimate_revision": "NOT_CALCULATED_BY_TARGET_REVISIONS",
        "rank_with_no_earnings_consensus": False,
        "actionable": False,
    }


def earnings_consensus_revision(before, after, *, now=None,
                                max_age_days=100, min_contributors=3):
    """Same fiscal period, metric and accounting basis on both observations.

    Annual EPS/EBIT estimates frequently change denominator, discontinued
    operations, share count, or IFRS/APM accounting basis. Require explicit
    same-period comparable snapshots, never invent data from broker targets.
    """
    now = now or datetime.now(timezone.utc)
    if before is None or after is None:
        return {
            "status": "UNVERIFIED_EARNINGS_ESTIMATE_MOMENTUM",
            "reason": "missing_comparable_consensus_snapshots",
            "revision_pct": None,
        }
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("consensus_snapshot_must_be_mapping")
    fields = ("symbol", "fiscal_period", "accounting_basis", "metric", "currency")
    if any(before.get(k) != after.get(k) or not before.get(k) for k in fields):
        return {"status": "UNVERIFIED_EARNINGS_ESTIMATE_MOMENTUM",
                "reason": "different_security_period_or_accounting_basis",
                "revision_pct": None}
    if before.get("metric") not in ("EPS", "EBIT", "EBITA", "FCF"):
        return {"status": "UNVERIFIED_EARNINGS_ESTIMATE_MOMENTUM",
                "reason": "unsupported_earnings_metric", "revision_pct": None}
    old, new = before.get("consensus"), after.get("consensus")
    if not _positive(old) or not _positive(new):
        return {"status": "UNVERIFIED_EARNINGS_ESTIMATE_MOMENTUM",
                "reason": "nonpositive_or_missing_consensus_not_comparable",
                "revision_pct": None}
    if any(
        not isinstance(x.get("contributors"), int)
        or isinstance(x["contributors"], bool)
        or x["contributors"] < min_contributors
        or not _source(x.get("source"))
        for x in (before, after)
    ):
        return {"status": "UNVERIFIED_EARNINGS_ESTIMATE_MOMENTUM",
                "reason": "unverified_consensus_sources_or_coverage",
                "revision_pct": None}
    a, b = _date(before.get("as_of")), _date(after.get("as_of"))
    if (not a < b <= now
            or (now-b).total_seconds() > max_age_days*86400
            or (b-a).days < 7):
        return {"status": "UNVERIFIED_EARNINGS_ESTIMATE_MOMENTUM",
                "reason": "invalid_consensus_observation_window",
                "revision_pct": None}
    change = 100 * (float(new)/float(old)-1)
    return {
        "status": "VERIFIED_COMPARABLE_CONSENSUS_REVISIONS",
        "symbol": before["symbol"],
        "metric": before["metric"],
        "fiscal_period": before["fiscal_period"],
        "accounting_basis": before["accounting_basis"],
        "old": float(old), "new": float(new),
        "revision_pct": round(change, 2),
        "direction": "UP" if change > .1 else "DOWN" if change < -.1 else "FLAT",
        "as_of": b.isoformat(),
        "contributors": min(before["contributors"], after["contributors"]),
    }
