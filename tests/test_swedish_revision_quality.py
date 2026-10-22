"""Elekta analyst revisions: never mistake Morningstar fair value for consensus."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from src.swedish_revision_quality import inspect_analyst_revisions


NOW = datetime(2026, 10, 22, 12, 40, tzinfo=timezone.utc)
ISIN = "SE0000163628"


def fixture():
    return json.loads(Path(
        "data/elekta_analyst_revisions_2026_10_22.json"
    ).read_text(encoding="utf-8"))


def review(data=None, **kwargs):
    data = fixture() if data is None else data
    return inspect_analyst_revisions(
        data["records"], isin=ISIN, now=NOW,
        short_interest=data.get("short_interest"),
        earnings_consensus_snapshots=data.get("earnings_consensus_snapshots"),
        **kwargs
    )


def test_elekta_morningstar_cut_kept_separate_from_bank_target_revisions():
    result = review()
    fair = result["fair_value_revisions"]
    assert fair["count"] == 1 and fair["lowered"] == 1
    assert fair["changes"][0]["change_pct"] == -20.0
    banks = result["price_target_revisions"]
    assert banks["count"] == 7
    assert banks["raised"] == 3
    assert banks["lowered"] == 4
    assert banks["median_pct_change"] < 0
    assert all(row["house"] != "Morningstar / Alex Morozov"
               for row in banks["changes"])


def test_high_short_is_visible_but_not_automatic_bear_probability():
    result = review()
    assert result["short_interest"]["verified"]
    assert result["short_interest"]["percentage"] == 15.39
    assert result["short_interest"]["high_short_risk"] is True
    assert result["not_a_probability"] is True


def test_missing_eps_consensus_history_is_unknown_not_neutral_or_positive():
    result = review()
    assert result["earnings_consensus_momentum"]["direction"] == "UNKNOWN"
    assert result["data_gate"] == "RESEARCH_ONLY_CRITICAL_DATA_MISSING"
    assert result["actionable"] is False
    assert result["trading_signal"] is None
    assert "critical_data_missing_no_buy_verdict" in result["warnings"]


def test_one_raised_target_cannot_override_majority_cuts():
    data = fixture()
    result = review(data)
    assert "more_target_cuts_than_raises_in_observed_sample" in result["warnings"]


def test_data_wrong_isin_refused_not_grouped_into_wrong_stock():
    data = fixture()
    bad = deepcopy(data["records"][0])
    bad["isin"] = "SE0000115446"
    data["records"].append(bad)
    result = review(data)
    assert result["price_target_revisions"]["count"] == 7
    assert any(x["reason"] == "identity_mismatch"
               for x in result["rejected_records"])


def test_stale_short_interest_fails_closed():
    data = fixture()
    data["short_interest"]["as_of"] = "2026-09-01"
    result = review(data)
    assert result["short_interest"]["verified"] is False
    assert result["short_interest"]["high_short_risk"] is None


def test_stale_analyst_report_not_used_as_fresh_revision():
    data = fixture()
    data["records"][0]["effective_at"] = "2026-01-01"
    result = review(data)
    assert result["price_target_revisions"]["count"] == 6
    assert any(x["reason"] == "revision_outside_review_window"
               for x in result["rejected_records"])


def test_matching_fiscal_year_consensus_snapshots_can_verify_positive_momentum():
    data = fixture()
    data["earnings_consensus_snapshots"] = [
        {"as_of": "2026-09-22", "fiscal_year": "2027",
         "eps_basis": "ADJUSTED", "currency": "SEK", "eps": 2.0,
         "analyst_count": 10, "source": "https://example.com/eps-history"},
        {"as_of": "2026-10-22", "fiscal_year": "2027",
         "eps_basis": "ADJUSTED", "currency": "SEK", "eps": 2.2,
         "analyst_count": 10, "source": "https://example.com/eps-history"},
    ]
    result = review(data)
    assert result["earnings_consensus_momentum"]["verified"]
    assert result["earnings_consensus_momentum"]["change_pct"] == 10.0
    assert result["earnings_consensus_momentum"]["direction"] == "UP"
    assert result["data_gate"] == "DILIGENCE_DATA_COMPLETE_FOR_REVIEW"
    assert not result["actionable"]


def test_different_fiscal_years_cannot_pretend_to_be_momentum():
    data = fixture()
    data["earnings_consensus_snapshots"] = [
        {"as_of": "2026-09-22", "fiscal_year": "2026",
         "eps_basis": "ADJUSTED", "currency": "SEK", "eps": 3.0,
         "analyst_count": 10, "source": "https://example.com/eps"},
        {"as_of": "2026-10-22", "fiscal_year": "2027",
         "eps_basis": "ADJUSTED", "currency": "SEK", "eps": 3.2,
         "analyst_count": 10, "source": "https://example.com/eps"},
    ]
    result = review(data)
    assert not result["earnings_consensus_momentum"]["verified"]
    assert result["earnings_consensus_momentum"]["direction"] == "UNKNOWN"


def test_disallow_analyst_drafts_without_https_source():
    data = fixture()
    data["records"][0]["source"] = "https://"
    result = review(data)
    assert result["price_target_revisions"]["count"] == 6
    assert any(x["reason"] == "noncomparable_or_uncited_revision"
               for x in result["rejected_records"])


def test_duplicate_same_house_only_latest_target_counts():
    data = fixture()
    data["records"].append({
        "isin": ISIN, "kind": "price_target",
        "house": "Pareto Securities",
        "previous": 60, "current": 65,
        "effective_at": "2026-08-01", "currency": "SEK",
        "horizon_months": 12, "source": "https://example.org/research"
    })
    result = review(data)
    assert result["price_target_revisions"]["count"] == 7


def test_revisions_dont_include_articles_or_stocktwits_sentiment():
    data = fixture()
    data["records"][0]["stocktwits_sentiment"] = 100
    data["records"][0]["publisher_opinion"] = "STRONG BUY"
    assert review(data)["price_target_revisions"] == review()["price_target_revisions"]
