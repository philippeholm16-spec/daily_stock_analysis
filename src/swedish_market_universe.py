"""Fail-closed Nasdaq Stockholm main-market universe validation.

This module does not scrape, guess, or generate a stock list. An upstream
provider must supply a complete, dated, licensed/authorized listing snapshot.
No tradeable universe is produced unless provenance and coverage are verified.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


MAIN_SEGMENTS = frozenset({"Large Cap", "Mid Cap", "Small Cap"})


@dataclass(frozen=True)
class Listing:
    isin: str
    symbol: str
    mic: str
    segment: str
    currency: str
    instrument_type: str
    active: bool


@dataclass(frozen=True)
class UniverseSnapshot:
    source: str
    as_of: datetime
    complete_main_market: bool
    listings: tuple[Listing, ...]


class UniverseError(ValueError):
    """Listing data is not trustworthy enough to scan."""


def validate_universe(snapshot: UniverseSnapshot, *, now: datetime | None = None,
                      max_age_hours: int = 24) -> tuple[Listing, ...]:
    """Return verified equities or raise; never silently accept partial data.

    Complete coverage must be explicitly asserted by the provider and verified
    operationally upstream; this flag alone is not independent proof.
    """
    current = now or datetime.now(timezone.utc)
    if not snapshot.source or not snapshot.source.strip():
        raise UniverseError("missing_source")
    if not snapshot.complete_main_market:
        raise UniverseError("unverified_or_partial_coverage")
    if (snapshot.as_of is None or snapshot.as_of.tzinfo is None
            or current.tzinfo is None):
        raise UniverseError("missing_timezone_aware_timestamp")
    age = (current - snapshot.as_of).total_seconds()
    if age < 0 or age > max_age_hours * 3600:
        raise UniverseError("stale_or_future_universe")
    if not snapshot.listings:
        raise UniverseError("empty_universe")
    result = []
    seen = set()
    for listing in snapshot.listings:
        if listing.mic != "XSTO" or listing.segment not in MAIN_SEGMENTS:
            raise UniverseError("unexpected_market_or_segment")
        if listing.currency != "SEK" or listing.instrument_type != "EQUITY" or not listing.active:
            raise UniverseError("non_equity_or_inactive_listing")
        if (not isinstance(listing.isin, str) or len(listing.isin) != 12
                or not listing.isin[:2].isalpha() or not listing.isin[2:].isalnum()
                or not isinstance(listing.symbol, str) or not listing.symbol.strip()):
            raise UniverseError("invalid_instrument_identity")
        identity = (listing.isin, listing.symbol)
        if identity in seen:
            raise UniverseError("duplicate_listing")
        seen.add(identity)
        result.append(listing)
    return tuple(result)
