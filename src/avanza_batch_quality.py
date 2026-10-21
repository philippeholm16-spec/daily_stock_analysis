"""Safe quote-batch ranking for data coverage, not trade signals."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Coverage:
    requested: int
    received: int
    valid: int
    realtime: int
    rejected: int
    complete: bool


def validate_quotes(requested_ids, records):
    """Require one unique matching quote per requested instrument."""
    ids = list(requested_ids)
    if len(ids) != len(set(ids)) or any(not str(i).isascii() or not str(i).isdecimal() for i in ids):
        raise ValueError("invalid_requested_ids")
    accepted = {}
    rejected = {}
    for record in records:
        oid = str(record.get("order_book_id", ""))
        if oid not in ids or oid in accepted or oid in rejected:
            raise ValueError("unexpected_or_duplicate_quote")
        price = record.get("last")
        volume = record.get("totalVolumeTraded")
        valid = (isinstance(price, (float, int)) and not isinstance(price, bool)
                 and isfinite(price) and price > 0
                 and isinstance(volume, (float, int)) and not isinstance(volume, bool)
                 and isfinite(volume) and volume >= 0 and float(volume).is_integer())
        if valid:
            accepted[oid] = {"last_price": float(price), "volume": int(volume),
                             "realtime": record.get("isRealTime") is True,
                             "actionable": False}
        else:
            rejected[oid] = "invalid_price_or_volume"
    missing = set(ids) - set(accepted) - set(rejected)
    for oid in missing:
        rejected[oid] = "missing_quote"
    return Coverage(len(ids), len(records), len(accepted),
                    sum(int(q["realtime"]) for q in accepted.values()),
                    len(rejected), len(accepted) == len(ids)), accepted, rejected
