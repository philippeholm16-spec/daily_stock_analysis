"""Corroborate IBKR streaming BBO with separately timestamped bid/ask ticks.

IBKR tickByTickBidAsk reports no exchange. reqMktData's bidExch/askExch
fields describe streaming BBO's source. It is UNSAFE to copy the tick-by-
tick price while pretending the stream's exchange codes attest its venue.

Require both streams' bid and ask to match within one minimum tick and the
streaming BBO/venue observations to be recent. In production, use the
reqMktData BBO prices (with their venue evidence), not unproven other prices.
An observed local BBO update is NOT an exchange-timestamp guarantee.
"""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class BookCorroboration:
    verified: bool
    reason: str
    primary_bid: float | None = None
    primary_ask: float | None = None


def _positive(n):
    return isinstance(n, (int, float)) and not isinstance(n, bool) and isfinite(n) and n > 0


def verify_streaming_book(*, stream_bid, stream_ask, tick_bid, tick_ask,
                          min_tick, streaming_bid_age, streaming_ask_age,
                          bid_venue_age, ask_venue_age,
                          max_bbo_age_seconds=15,
                          max_venue_age_seconds=60):
    if not all(_positive(x) for x in
               (stream_bid, stream_ask, tick_bid, tick_ask, min_tick)):
        return BookCorroboration(False, "missing_or_invalid_streaming_book")
    if stream_bid >= stream_ask or tick_bid >= tick_ask:
        return BookCorroboration(False, "locked_or_crossed_book")
    ages = (streaming_bid_age, streaming_ask_age)
    if any(not isinstance(x, (int, float)) or isinstance(x, bool)
           or not isfinite(x) or x < 0 or x > max_bbo_age_seconds for x in ages):
        return BookCorroboration(False, "stale_streaming_book_update")
    code_ages = (bid_venue_age, ask_venue_age)
    if any(not isinstance(x, (int, float)) or isinstance(x, bool)
           or not isfinite(x) or x < 0 or x > max_venue_age_seconds
           for x in code_ages):
        return BookCorroboration(False, "stale_or_missing_exchange_venue_codes")
    # Allow 1 minTick tolerance to accommodate occasional independent
    # callbacks while ensuring the chosen price is explicitly streaming BBO.
    if (abs(stream_bid - tick_bid) > min_tick + 1e-9
            or abs(stream_ask - tick_ask) > min_tick + 1e-9):
        return BookCorroboration(False, "tick_and_primary_bbo_disagree")
    return BookCorroboration(
        True, "two_streams_agree_primary_bbo_proven",
        float(stream_bid), float(stream_ask)
    )
