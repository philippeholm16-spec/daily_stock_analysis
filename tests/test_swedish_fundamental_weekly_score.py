"""Weekly Swedish value score is transparent, auditable and NOT a buy signal."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from src.swedish_fundamental_weekly_score import (
    MAX_SCORE, WEIGHTS, rank_weekly_watchlist, score_fundamental_watch
)

NOW = datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc)


def watchlist():
    document = json.loads(Path("data/swedish_research_2026_w43.json").read_text())
    return document["candidates"]


def test_all_7_grounded_weekly_opportunities_have_reproducible_scores():
    candidates = watchlist()
    result = rank_weekly_watchlist(candidates, now=NOW)
    assert len(candidates) == 7
    assert result["week"] == "2026-W43"
    assert result["candidate_count"] == 7
    assert sum(WEIGHTS.values()) == MAX_SCORE == 100
    assert [(r["symbol"], r["score"]) for r in result["ranked"]] == [
        ("SKF B", 76), ("ABB", 74), ("SKA B", 70),
        ("EKTA B", 69), ("ERIC B", 61), ("ESSITY B", 59), ("EVO", 53)
    ]
    assert all(row["actionable"] is False and row["trading_signal"] is None
               for row in result["ranked"])
    assert result["trading_signals_enabled"] is False
    assert result["fully_independent_live_technical_scan_done"] is False


def test_latest_stock_prices_are_explicitly_historical_reference():
    result = score_fundamental_watch(watchlist()[1], now=NOW)
    assert result["symbol"] == "ABB"
    assert result["reference_price_sek"] == 860.6
    assert result["price_as_of"].startswith("2026-10-21")
    assert result["today_buy_status"] == "NOT_VERIFIED_WITH_XSTO_REALTIME_AND_STOCK_ANALYST"


def test_each_factor_has_source_link_and_explanation():
    for item in watchlist():
        for key in WEIGHTS:
            evidence = item["factors"][key]
            assert evidence["sources"]
            assert all(url.startswith("https://") for url in evidence["sources"])
            assert len(evidence["explanation"]) >= 16


def test_press_headline_not_part_of_calculation():
    x = watchlist()[1]
    y = deepcopy(x)
    y["publisher_recommendation"] = "All newspapers say BUY"
    y["headline_score"] = 999
    assert score_fundamental_watch(x, now=NOW) == score_fundamental_watch(y, now=NOW)


def test_manual_points_must_never_exceed_component_weight():
    entry = deepcopy(watchlist()[0])
    entry["factors"]["valuation"]["points"] = 31
    with pytest.raises(ValueError, match="out_of_bounds"):
        score_fundamental_watch(entry, now=NOW)


def test_uncited_or_missing_factor_fails_closed():
    entry = deepcopy(watchlist()[0])
    entry["factors"]["fundamentals"]["sources"] = []
    with pytest.raises(ValueError, match="uncited"):
        score_fundamental_watch(entry, now=NOW)
    entry = deepcopy(watchlist()[0])
    del entry["factors"]["entry_timing"]
    with pytest.raises(ValueError, match="all_five"):
        score_fundamental_watch(entry, now=NOW)


def test_future_prices_and_stale_reference_never_admitted():
    entry = deepcopy(watchlist()[0])
    entry["price_as_of"] = (NOW+timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="reference_price_too_stale"):
        score_fundamental_watch(entry, now=NOW)
    entry = deepcopy(watchlist()[0])
    entry["price_as_of"] = (NOW-timedelta(days=8)).isoformat()
    with pytest.raises(ValueError, match="reference_price_too_stale"):
        score_fundamental_watch(entry, now=NOW)


def test_wrong_exchange_cannot_fake_stockholm_share():
    entry = deepcopy(watchlist()[1])
    entry["mic"] = "XNAS"
    with pytest.raises(ValueError, match="unsupported"):
        score_fundamental_watch(entry, now=NOW)


def test_duplicate_share_class_uses_newest_review_only():
    first = deepcopy(watchlist()[1])
    second = deepcopy(first)
    second["reviewed_at"] = (NOW-timedelta(minutes=10)).isoformat()
    second["factors"]["valuation"]["points"] = 18
    result = rank_weekly_watchlist([first, second], now=NOW)
    assert result["candidate_count"] == 1
    assert result["ranked"][0]["score"] == 75


def test_different_iso_weeks_must_not_mix_in_one_ranking():
    items = deepcopy(watchlist()[:2])
    items[1]["reviewed_at"] = "2026-10-18T10:00:00+02:00"
    with pytest.raises(ValueError, match="single_iso_week"):
        rank_weekly_watchlist(items, now=NOW)
