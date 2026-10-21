"""Test that technical targets come from historically confirmed resistance."""
from src.technical_price_levels import derive_levels


def bars(*, resistance=True, single_spike=False):
    values = []
    for i in range(40):
        close = 100.0 + i * 0.05
        spike = ((i in (28, 30)) if resistance else (i == 30 and single_spike))
        high = 110 if spike else close + 0.04
        values.append({"open": close - 0.03, "close": close,
                       "high": high, "low": close - 0.15, "volume": 1500})
    return values


def test_two_resistance_touches_produce_observed_target():
    levels = derive_levels(bars(), entry=101.95)
    assert levels.target == 110
    assert levels.resistance_touches >= 2
    assert levels.stop < levels.support < 101.95
    assert levels.atr14 > 0
    assert levels.target_reason == "repeated_historical_resistance"


def test_single_spike_is_not_a_price_target():
    levels = derive_levels(bars(resistance=False, single_spike=True), entry=101.95)
    assert levels.target is None
    assert levels.target_reason == "resistance_requires_repeated_observations"


def test_no_overhead_resistance_means_no_target():
    levels = derive_levels(bars(resistance=False), entry=101.95)
    assert levels.target is None
    assert levels.target_reason == "no_observed_resistance_above_entry"


def test_later_unseen_price_cannot_create_historical_target():
    data = bars(resistance=False)
    baseline = derive_levels(data, entry=101.95)
    # No future candles are supplied, so the model cannot assume price will hit 110.
    assert baseline.target is None


def test_short_series_fails_closed():
    try:
        derive_levels(bars()[:15], entry=101.95)
        raise AssertionError("history should have been rejected")
    except ValueError as exc:
        assert "insufficient" in str(exc)
