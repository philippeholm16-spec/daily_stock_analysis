"""Read-only Avanza MCP adapter boundary (offline, no network calls).

The upstream Avanza MCP project is unofficial. This module deliberately
does not authenticate, launch a server, scrape, or call Avanza endpoints.
It converts explicitly supplied tool output into a *non-actionable* quote.
A separate approved integration and timestamp/coverage validation are
required before data may be considered for trading signals.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping


class AvanzaDataError(ValueError):
    """Reject unsupported or incomplete provider output."""


@dataclass(frozen=True)
class AvanzaQuote:
    order_book_id: str
    price: float
    volume: int
    as_of: datetime | None
    timestamp_verified: bool = False
    actionable: bool = False


def parse_public_quote(payload: Mapping[str, Any], *, order_book_id: str) -> AvanzaQuote:
    """Parse a minimal *normalized* fixture, never assert real-time status.

    This is not the Avanza MCP raw response schema. A future mapping from the
    actual get_stock_quote response must be validated with real fixtures.
    """
    if not isinstance(payload, Mapping) or not str(order_book_id).isdigit():
        raise AvanzaDataError("invalid_payload_or_instrument_id")
    price = payload.get("last_price")
    volume = payload.get("volume")
    if (isinstance(price, bool) or not isinstance(price, (int, float))
            or not isfinite(price) or price <= 0):
        raise AvanzaDataError("invalid_or_missing_price")
    if isinstance(volume, bool) or not isinstance(volume, int) or volume < 0:
        raise AvanzaDataError("invalid_or_missing_volume")
    timestamp = payload.get("as_of")
    parsed = None
    if timestamp is not None:
        if not isinstance(timestamp, str):
            raise AvanzaDataError("invalid_timestamp")
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AvanzaDataError("invalid_timestamp") from exc
        if parsed.tzinfo is None:
            raise AvanzaDataError("timestamp_without_timezone")
        parsed = parsed.astimezone(timezone.utc)
    return AvanzaQuote(order_book_id=str(order_book_id), price=float(price),
                       volume=volume, as_of=parsed)
