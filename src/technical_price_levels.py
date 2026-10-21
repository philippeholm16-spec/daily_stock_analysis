"""Price-derived support, volatility buffer and confirmed resistance.

This is a strictly historical, illustrative technical level model. It does
not fit desired risk/reward by manufacturing a target. Repeated resistance
touches are required; a single high-price outlier is not a price target.
"""
from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class StructuralLevels:
    stop: float
    target: float | None
    atr14: float
    support: float
    resistance_touches: int
    target_reason: str


def derive_levels(bars, *, entry):
    """Use only observed bars at or before analysis time; no future bars."""
    if len(bars) < 25 or not 0 < entry:
        raise ValueError("insufficient_price_history")
    spans = []
    for index in range(len(bars) - 14, len(bars)):
        candle = bars[index]
        prev = bars[index - 1]
        spans.append(max(
            candle["high"] - candle["low"],
            abs(candle["high"] - prev["close"]),
            abs(candle["low"] - prev["close"]),
        ))
    atr = mean(spans)
    if atr <= 0:
        raise ValueError("zero_historical_volatility")
    recent = bars[-7:]
    support = min(bar["low"] for bar in recent)
    stop = support - max(0.15 * atr, entry * 0.001)

    # Pre-existing resistance above entry, prior 35 bars (exclude current).
    history = bars[max(0, len(bars) - 36):-1]
    levels = [(float(bar["high"]), idx) for idx, bar in enumerate(history)
              if bar["high"] > entry]
    if not levels:
        return StructuralLevels(stop, None, atr, support, 0,
                                "no_observed_resistance_above_entry")

    # Confirm resistance by >=2 touches separated by >=2 candles.
    # This rejects single spike highs and avoids inventing a target via RR.
    tolerance = max(0.15 * atr, entry * 0.0005)
    options = []
    for price, idx in levels:
        touch_points = [(value, index) for value, index in levels
                        if abs(value - price) <= tolerance]
        distinct = {i for _, i in touch_points}
        if len(distinct) >= 2 and max(distinct) - min(distinct) >= 2:
            # Target at the lower boundary of verified resistance, not above.
            options.append((min(v for v, _ in touch_points), len(distinct)))
    if not options:
        return StructuralLevels(stop, None, atr, support, 0,
                                "resistance_requires_repeated_observations")

    # First encountered confirmed overhead resistance; a higher distant
    # target must not be cherry-picked to inflate RR.
    target, touches = min(options, key=lambda pair: pair[0])
    return StructuralLevels(stop, target, atr, support, touches,
                            "repeated_historical_resistance")
