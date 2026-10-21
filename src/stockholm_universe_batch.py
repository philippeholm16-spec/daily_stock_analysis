"""Plan complete XSTO scans in bounded, segment-balanced API batches.

No listing is invented. A real, independently authorized complete Nasdaq
Stockholm source is mandatory. This lets the scanner move beyond publishers,
but does not itself supply the licensed reference data.
"""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from math import ceil

from src.complete_market_coverage import audit_complete_xsto

SEGMENTS = ("Large Cap", "Mid Cap", "Small Cap")


@dataclass(frozen=True)
class BatchPlan:
    reference_hash: str
    complete_reference_audit: bool
    batch_index: int
    batch_count: int
    batch_size: int
    total_stocks: int
    stocks: tuple[dict, ...]

    def as_dict(self):
        return asdict(self)


def create_batch_plan(reference, mapping, *, index, size=10, now=None):
    """Balance Large/Mid/Small Cap, then sweep all verified ISINs once.

    Caller must externally validate source authorizations and exact completeness.
    Do not conflate this coverage of IDs with timely successful quote collection.
    """
    if (isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 12
            or isinstance(index, bool) or not isinstance(index, int) or index < 0):
        raise ValueError("invalid_batch_bounds")
    audit = audit_complete_xsto(reference, mapping, now=now)
    if not audit.complete:
        raise ValueError("market_reference_not_completely_verified")
    holdings = mapping["listings"]
    pools = {segment: [] for segment in SEGMENTS}
    for item in holdings:
        pools[item["segment"]].append(item)
    for segment in SEGMENTS:
        pools[segment].sort(key=lambda x: (x["symbol"], x["isin"]))
    balanced = []
    while any(pools.values()):
        for segment in SEGMENTS:
            if pools[segment]:
                balanced.append(pools[segment].pop(0))
    count = ceil(len(balanced) / size)
    if index >= count:
        raise ValueError("batch_index_out_of_range")
    source_record = {
        "source": reference["source"],
        "as_of": reference["as_of"],
        "listings": sorted(
            reference["listings"], key=lambda row: (row["isin"], row["symbol"])
        ),
    }
    digest = sha256(json.dumps(source_record, sort_keys=True,
                                separators=(",", ":")).encode("utf-8")).hexdigest()
    lo = index * size
    subset = tuple({
        "isin": row["isin"],
        "symbol": row["symbol"],
        "mic": row["mic"],
        "segment": row["segment"],
        "order_book_id": row["order_book_id"],
        "currency": row["currency"],
    } for row in balanced[lo:lo+size])
    return BatchPlan(digest, True, index, count, len(subset),
                     len(balanced), subset)


def audit_sweep(plans, *, expected_total, expected_hash):
    """Verify a set of completed batch plans sweeps each ISIN exactly once.

    No market-data completeness guarantee: this only audits the planned IDs.
    """
    indices, isins = set(), set()
    expected_count = None
    for plan in plans:
        if plan.reference_hash != expected_hash or not plan.complete_reference_audit:
            raise ValueError("reference_drift")
        if expected_count is None:
            expected_count = plan.batch_count
        if plan.batch_count != expected_count or plan.batch_index in indices:
            raise ValueError("duplicate_or_inconsistent_batches")
        indices.add(plan.batch_index)
        for instrument in plan.stocks:
            if instrument["isin"] in isins:
                raise ValueError("duplicate_instrument_across_batches")
            isins.add(instrument["isin"])
    return {
        "batch_count_expected": expected_count,
        "batches_seen": len(indices),
        "stocks_seen": len(isins),
        "all_reference_instruments_scheduled": (
            expected_count is not None and len(indices) == expected_count
            and len(isins) == expected_total
        ),
        "all_market_prices_verified": False,
    }
