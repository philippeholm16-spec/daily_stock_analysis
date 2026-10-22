"""Historical playback never uses future prices to create today's target."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from src.stockholm_walkforward import (
    analyze_at, simulate_exit, walk_forward_replay,
)


NOW = datetime(2026, 10, 21, 14, tzinfo=timezone.utc)
ISIN = "SE0000115446"


def history(n=80):
    rows = []
    for i in range(n):
        close = 100 + 0.05 * i
        rows.append({
            "at": NOW + timedelta(minutes=10*i),
            "open": close-0.03,
            "high": 110 if i in (28, 30) else close + 0.04,
            "low": close-0.15,
            "close": close,
            "volume": 5000 if i == 39 else 1500,
        })
    return rows


def test_historical_evidence_stops_at_current_analysis_bar():
    rows = history()
    first = analyze_at(rows, 40, ticker="EXAM", isin=ISIN, window=40)
    changed_future = deepcopy(rows)
    changed_future[42]["high"] = 999
    changed_future[50]["close"] = 1
    same = analyze_at(changed_future, 40, ticker="EXAM", isin=ISIN, window=40)
    assert first == same
    assert first["status"] == "ANALYZED_INDICATIVE_SETUP"
    assert first["opportunity_grade"] == "VERY_GOOD"


def test_both_stop_and_target_hit_same_bar_counts_as_loss():
    analysis = {
        "status": "ANALYZED_INDICATIVE_SETUP",
        "entry_price": 100, "lowest_sell_point": 98,
        "sell_point": 106, "quantity": 10, "max_risk_sek": 23,
    }
    replay = simulate_exit(
        analysis,
        [{"open": 100, "high": 107, "low": 97, "close": 103}],
    )
    assert replay["outcome"] == "STOP_AMBIGUOUS"
    assert replay["exit_price"] == 98
    assert replay["r_multiple"] < 0


def test_gap_below_stop_can_exceed_planned_risk():
    analysis = {
        "status": "ANALYZED_INDICATIVE_SETUP",
        "entry_price": 100, "lowest_sell_point": 98,
        "sell_point": 106, "quantity": 10, "max_risk_sek": 23,
    }
    replay = simulate_exit(
        analysis,
        [{"open": 100, "high": 101, "low": 99, "close": 100},
         {"open": 95, "high": 103, "low": 94, "close": 100}],
    )
    assert replay["outcome"] == "STOP_GAP"
    assert replay["exit_price"] == 95
    assert replay["r_multiple"] < -1


def test_walk_forward_emits_explicit_unverified_performance_metrics():
    output = walk_forward_replay(
        history(), ticker="EXAM", isin=ISIN,
        lookback=40, horizon=10, step=10
    )
    assert output["windows"] >= 2
    assert output["very_good_signals"] >= 1
    assert output["performance_verified"] is False
    assert output["trading_enabled"] is False
    assert output["very_good_signals"] == len(output["trades"])
    assert output["win_rate_all_trades"] is not None


def test_short_or_time_unsorted_history_fails():
    with pytest.raises(ValueError, match="insufficient"):
        walk_forward_replay(history()[:43], ticker="EXAM", isin=ISIN,
                            lookback=40, horizon=10)
    invalid = history()
    invalid[50]["at"] = invalid[49]["at"]
    with pytest.raises(ValueError, match="unsorted"):
        walk_forward_replay(invalid, ticker="EXAM", isin=ISIN,
                            lookback=40, horizon=10)


def test_no_trade_signals_produces_no_fake_win_rate():
    bars = history()
    for b in bars:
        b["volume"] = 1
    replay = walk_forward_replay(bars, ticker="EXAM", isin=ISIN,
                                 lookback=40, horizon=10)
    assert replay["very_good_signals"] == 0
    assert replay["win_rate_all_trades"] is None
    assert replay["profit_factor_r"] is None
