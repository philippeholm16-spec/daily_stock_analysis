"""Fail-closed audit of Nasdaq Stockholm coverage against independent reference data.

The reference file must come from an authorized full-universe provider. This
code checks the match; it cannot certify a provider's license or truthfulness.
Do not confuse Avanza text search or an ESMA ISIN set with a complete listing
including Nasdaq segment and Avanza book ID.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re


ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")
SEGMENTS = {"Large Cap", "Mid Cap", "Small Cap"}


@dataclass(frozen=True)
class CoverageReport:
    reference_count: int
    mapped_count: int
    missing_isins: tuple[str, ...]
    extra_isins: tuple[str, ...]
    mismatched: tuple[str, ...]
    invalid_rows: tuple[str, ...]
    reference_fresh: bool
    reference_independent: bool
    source_verified: bool
    complete: bool

    def as_dict(self):
        return asdict(self)


def audit_complete_xsto(reference, avanza_manifest, *, now=None,
                        max_age_hours=24):
    """Compare exact (ISIN, ticker, MIC, segment) plus unique book IDs.

    reference and avanza_manifest are dictionaries with 'source', 'as_of',
    and 'listings'. reference must declare complete_main_market=true and
    source_verified=true; declarations must be checked by an operator against
    the authorized upstream data and its coverage documentation.
    """
    now = now or datetime.now(timezone.utc)
    invalid = []
    ref_index, mapped_index = {}, {}
    independent = (bool(reference.get("source")) and bool(avanza_manifest.get("source"))
                   and reference["source"] != avanza_manifest["source"])
    verified = reference.get("source_verified") is True
    try:
        stamp = datetime.fromisoformat(reference["as_of"].replace("Z", "+00:00"))
        age = (now - stamp).total_seconds()
        fresh = stamp.tzinfo is not None and 0 <= age <= max_age_hours * 3600
    except (KeyError, TypeError, ValueError):
        fresh = False
    if reference.get("complete_main_market") is not True:
        invalid.append("reference_does_not_claim_complete_market")
    for dataset, index, prefix in (
        (reference, ref_index, "reference"),
        (avanza_manifest, mapped_index, "mapping")
    ):
        rows = dataset.get("listings", [])
        if not isinstance(rows, list):
            invalid.append(prefix + ":invalid_list")
            continue
        seen_book_ids = set()
        for row_num, row in enumerate(rows):
            if not isinstance(row, dict):
                invalid.append(f"{prefix}:{row_num}:not_object")
                continue
            isin = row.get("isin")
            symbol = row.get("symbol")
            mic = row.get("mic")
            segment = row.get("segment")
            if (not isinstance(isin, str) or not ISIN.fullmatch(isin)
                    or not isinstance(symbol, str) or not symbol.strip()
                    or mic != "XSTO" or segment not in SEGMENTS):
                invalid.append(f"{prefix}:{row_num}:invalid_security")
                continue
            if isin in index:
                invalid.append(f"{prefix}:{row_num}:duplicate_isin")
            index[isin] = (symbol.strip(), mic, segment)
            if prefix == "mapping":
                book = row.get("order_book_id")
                if not isinstance(book, str) or not book.isascii() or not book.isdecimal():
                    invalid.append(f"mapping:{row_num}:invalid_order_book_id")
                elif book in seen_book_ids:
                    invalid.append(f"mapping:{row_num}:duplicate_order_book_id")
                else:
                    seen_book_ids.add(book)
                if row.get("active") is not True or row.get("instrument_type") != "EQUITY":
                    invalid.append(f"mapping:{row_num}:inactive_or_non_equity")
    missing = tuple(sorted(ref_index.keys() - mapped_index.keys()))
    extra = tuple(sorted(mapped_index.keys() - ref_index.keys()))
    mismatched = tuple(sorted(k for k in ref_index.keys() & mapped_index.keys()
                             if ref_index[k] != mapped_index[k]))
    complete = (bool(ref_index) and fresh and independent and verified
                and not invalid and not missing and not extra and not mismatched)
    return CoverageReport(
        reference_count=len(ref_index), mapped_count=len(mapped_index),
        missing_isins=missing, extra_isins=extra, mismatched=mismatched,
        invalid_rows=tuple(invalid), reference_fresh=fresh,
        reference_independent=independent, source_verified=verified,
        complete=bool(complete))
