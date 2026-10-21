"""Offline, provider-shaped Stock Analyst Sweden tests (no publisher ratings)."""
from datetime import datetime, timedelta, timezone
from copy import deepcopy

import pytest

from src.stockholm_stock_analyst import analyze_xsto_candidate, validate_chart

NOW = datetime(2026, 10, 21, 14, tzinfo=timezone.utc)


def chart(*, with_resistance=True):
    rows = []
    for i in range(40):
        close = 100.0 + i * 0.05
        hi = 110.0 if i == 30 and with_resistance else close + 0.15
        rows.append({
            "timestamp": int((NOW - timedelta(minutes=(39-i)*10)).timestamp()*1000),
            "open": round(close-0.05, 2), "high": round(hi, 2),
            "low": round(close-0.2, 2), "close": round(close, 2),
            "totalVolumeTraded": 2200 if i == 39 else 500,
        })
    return {"data": {"ohlc": rows,
                     "metadata": {"resolution": {"chartResolution": "ten_minutes"}}},
            "pagination": {"total": 40, "offset": 0, "returned": 40}}


def stock():
    return {
        "mic": "XSTO", "identity_source": "avanza_get_stock_info",
        "ticker": "EXAM", "isin": "SE0000115446",
        "last_price": 101.95, "volume": 150000,
        "turnover_proxy_sek": 10_000_000, "spread_pct": 0.15,
        # These press fields should NEVER be included in technical scoring.
        "headline": "EXAM är årets bästa köptips",
        "source": "Placera", "research_score": 10,
    }


def test_all_levels_derived_from_prices_not_publisher_opinion():
    result = analyze_xsto_candidate(stock(), chart(), now=NOW, capital_sek=15000)
    assert result["status"] == "ANALYZED_INDICATIVE_SETUP"
    assert 0 < result["lowest_sell_point"] < result["entry_price"] < result["sell_point"]
    assert result["sell_point"] == 110
    assert result["potential_pct"] == round((110 / 101.95 - 1)*100, 2)
    assert result["net_rr"] >= 2
    assert result["max_risk_sek"] <= 150
    assert result["source_news_opinion_used"] is False
    assert result["actionable"] is False


def test_change_press_opinion_no_effect():
    a = stock()
    b = deepcopy(a)
    b["headline"] = "EXAM: sälj allt genast"
    b["research_score"] = 0
    b["source"] = "Dagens industri"
    x = analyze_xsto_candidate(a, chart(), now=NOW)
    y = analyze_xsto_candidate(b, chart(), now=NOW)
    assert x == y


def test_without_observed_resistance_never_fabricate_sell_target():
    result = analyze_xsto_candidate(stock(), chart(with_resistance=False), now=NOW)
    assert result["status"] == "ANALYZED_NO_VALID_SETUP"
    assert result["sell_point"] is None
    assert result["potential_pct"] is None


def test_latest_page_required_to_prevent_stale_first_page_bias():
    sample = chart()
    sample["pagination"] = {"total": 120, "offset": 0, "returned": 40}
    assert analyze_xsto_candidate(stock(), sample, now=NOW)["status"] == "ANALYSIS_UNAVAILABLE"


def test_quote_identity_and_price_mismatch_fail_closed():
    sample = stock()
    sample["last_price"] = 124.0
    assert analyze_xsto_candidate(sample, chart(), now=NOW)["status"] == "ANALYSIS_UNAVAILABLE"
    sample = stock()
    sample["identity_source"] = "publisher_headline"
    assert analyze_xsto_candidate(sample, chart(), now=NOW)["status"] == "ANALYSIS_UNAVAILABLE"


def test_invalid_candle_series_rejected():
    sample = chart()
    sample["data"]["ohlc"][2]["low"] = 120
    assert analyze_xsto_candidate(stock(), sample, now=NOW)["status"] == "ANALYSIS_UNAVAILABLE"


def test_stale_bars_rejected():
    assert analyze_xsto_candidate(stock(), chart(), now=NOW + timedelta(days=8))["status"] == "ANALYSIS_UNAVAILABLE"


def test_low_liquidity_or_nonpositive_volume_no_fake_rvol():
    sample = chart()
    for row in sample["data"]["ohlc"]:
        row["totalVolumeTraded"] = 0
    result = analyze_xsto_candidate(stock(), sample, now=NOW)
    assert result["relative_volume_vs_prior20"] is None


def test_chart_resolution_wrong_fails():
    sample = chart()
    sample["data"]["metadata"]["resolution"]["chartResolution"] = "week"
    with pytest.raises(ValueError, match="incomplete_or_unsupported"):
        validate_chart(sample, now=NOW)
