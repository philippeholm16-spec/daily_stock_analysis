"""Regression checks: multi-broker revisions cannot become a buy signal."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from src.swedish_revision_momentum import (
    earnings_consensus_revision, target_revision_momentum
)
from src.swedish_investment_due_diligence import (
    evaluate_investment_readiness, evaluate_research_comparison
)

NOW = datetime(2026, 10, 22, 12, 40, tzinfo=timezone.utc)


def records():
    return json.loads(
        Path("data/swedish_revision_evidence_2026_w43.json").read_text()
    )["companies"]


def test_week43_measured_broker_revision_breadth_is_sensible():
    results = evaluate_research_comparison(records(), now=NOW)
    assert [x["symbol"] for x in results["stocks"]] == [
        "SKF B", "EKTA B", "ABB"
    ]
    by_symbol = {x["symbol"]: x for x in results["stocks"]}
    skf = by_symbol["SKF B"]["broker_momentum"]
    elekta = by_symbol["EKTA B"]["broker_momentum"]
    abb = by_symbol["ABB"]["broker_momentum"]
    assert (skf["positive_brokers"], skf["negative_brokers"]) == (12, 1)
    assert skf["momentum_label"] == "POSITIVE_BROKER_REVISION_BREADTH"
    assert (elekta["positive_brokers"], elekta["negative_brokers"]) == (3, 3)
    assert elekta["momentum_label"] == "MIXED_BROKER_REVISION_BREADTH"
    assert (abb["positive_brokers"], abb["negative_brokers"]) == (0, 3)
    assert abb["momentum_label"] == "NEGATIVE_BROKER_REVISION_BREADTH"
    assert all(x["final_buy_opportunity_score"] is None for x in results["stocks"])
    assert results["ready_to_buy_count"] == 0


def test_morningstar_fair_value_reduction_not_counted_as_broker_consensus():
    ekta = records()[0]
    x = target_revision_momentum(
        ekta["broker_events"], symbol="EKTA B", now=NOW
    )
    assert x["observations"] == 6
    assert len(x["fair_value_model_revisions"]) == 1
    assert x["fair_value_model_revisions"][0]["change_pct"] == -20
    assert x["fair_value_is_not_a_broker_consensus_target"] is True
    assert x["earnings_estimate_revision"] == "NOT_CALCULATED_BY_TARGET_REVISIONS"


def test_fi_short_interest_high_for_elekta_and_material_for_skf():
    output = {x["symbol"]: x for x in evaluate_research_comparison(
        records(), now=NOW)["stocks"]}
    assert output["EKTA B"]["short_interest"]["pct"] == 15.39
    assert "HIGH_FI_REPORTED_SHORT_INTEREST" in output["EKTA B"]["risk_flags"]
    assert "MATERIAL_NEGATIVE_FAIR_VALUE_MODEL_REVISION" in output["EKTA B"]["risk_flags"]
    assert output["SKF B"]["short_interest"]["pct"] == 7.37
    assert output["SKF B"]["short_interest"]["risk_level"] == "ELEVATED_SHORT_INTEREST"
    assert not output["ABB"]["short_interest"]["verified"]
    assert "missing_current_fi_short_interest" == output["ABB"]["short_interest"]["reason"]


def test_all_stocks_blocked_if_eps_revision_history_missing():
    for row in evaluate_research_comparison(records(), now=NOW)["stocks"]:
        assert "financial_estimate_changes" in row["missing_risk_modules"]
        assert "short_interest_level_and_trend" in row["missing_risk_modules"]
        assert row["earnings_momentum"]["revision_pct"] is None
        assert row["actionable"] is False
        assert row["reliable_probability_of_rise"] is None


def test_upgraded_rating_with_lower_target_never_cast_positive():
    abb = records()[2]
    x = deepcopy(abb["broker_events"][0])
    x["recommendation_old"] = "HOLD"
    x["recommendation_new"] = "BUY"
    out = target_revision_momentum([x], symbol="ABB", now=NOW,
                                   minimum_brokers=1)
    assert out["momentum_label"] == "NEGATIVE_BROKER_REVISION_BREADTH"


def test_broker_currency_can_differ_between_analysts_but_not_own_comparison():
    result = target_revision_momentum(
        records()[2]["broker_events"], symbol="ABB", now=NOW
    )
    assert result["observations"] == 3
    assert result["negative_brokers"] == 3
    assert result["median_broker_change_pct"] < 0


def test_multiple_updates_from_one_broker_have_single_vote():
    sample = records()[1]["broker_events"][:3]
    older = deepcopy(sample[0])
    older["as_of"] = "2026-10-19T12:00:00+02:00"
    older["old"], older["new"] = 270, 230
    result = target_revision_momentum(
        [older, *sample], symbol="SKF B", now=NOW
    )
    assert result["observations"] == 3
    assert result["positive_brokers"] == 3
    assert result["negative_brokers"] == 0


def test_unknown_thin_broker_coverage_fails_closed():
    out = target_revision_momentum(
        records()[1]["broker_events"][:1], symbol="SKF B", now=NOW
    )
    assert out["momentum_label"] == "UNKNOWN_INSUFFICIENT_BROKER_COVERAGE"
    assert out["rank_with_no_earnings_consensus"] is False


def test_wrong_security_and_future_target_never_counted():
    sample = deepcopy(records()[0]["broker_events"][0])
    sample["symbol"] = "ABB"
    with pytest.raises(ValueError, match="wrong_security"):
        target_revision_momentum([sample], symbol="EKTA B", now=NOW)
    sample["symbol"] = "EKTA B"
    sample["as_of"] = (NOW+timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="outside_lookback"):
        target_revision_momentum([sample], symbol="EKTA B", now=NOW)


def test_invalid_target_currency_or_nonpositive_rejected():
    for field, bad in [("currency",""),("old",0),("new",-1),("old",True)]:
        sample = deepcopy(records()[0]["broker_events"][0])
        sample[field] = bad
        with pytest.raises(ValueError):
            target_revision_momentum([sample], symbol="EKTA B", now=NOW)


def test_fair_value_masquerading_as_broker_is_rejected():
    sample = deepcopy(records()[0]["broker_events"][-1])
    sample["kind"] = "BROKER_TARGET"
    with pytest.raises(ValueError, match="valuation_model"):
        target_revision_momentum([sample], symbol="EKTA B", now=NOW)


def test_both_eps_snapshots_required_before_direction():
    item = records()[0]
    out = earnings_consensus_revision(
        item["estimated_earnings_revision_before"],
        item["estimated_earnings_revision_after"], now=NOW)
    assert out["status"] == "UNVERIFIED_EARNINGS_ESTIMATE_MOMENTUM"
    assert out["revision_pct"] is None


def eps_snap(value, date, *, metric="EPS", fiscal_period="FY2027",
             accounting_basis="ADJUSTED_DILUTED"):
    return {"symbol": "EKTA B", "fiscal_period": fiscal_period,
            "metric": metric, "accounting_basis": accounting_basis,
            "currency": "SEK", "consensus": value, "contributors": 10,
            "as_of": date, "source": "https://example.org/verified-snapshot"}


def test_apples_to_apples_consensus_revision_computes_without_target_price():
    early = eps_snap(2.0, "2026-09-20T11:00:00+02:00")
    later = eps_snap(2.2, "2026-10-21T11:00:00+02:00")
    out = earnings_consensus_revision(early, later, now=NOW)
    assert out["direction"] == "UP" and out["revision_pct"] == 10.0


def test_period_or_basis_change_rejected_as_consensus_revision():
    early = eps_snap(2.0, "2026-09-20T11:00:00+02:00")
    later = eps_snap(2.2, "2026-10-21T11:00:00+02:00",
                     fiscal_period="FY2028")
    out = earnings_consensus_revision(early, later, now=NOW)
    assert out["status"] == "UNVERIFIED_EARNINGS_ESTIMATE_MOMENTUM"
    later["fiscal_period"] = "FY2027"
    later["accounting_basis"] = "IFRS_REPORTED"
    out = earnings_consensus_revision(early, later, now=NOW)
    assert out["revision_pct"] is None


def test_consensus_broker_count_or_negative_eps_rejected():
    early = eps_snap(2.0, "2026-09-20T11:00:00+02:00")
    late = eps_snap(-2.2, "2026-10-21T11:00:00+02:00")
    assert earnings_consensus_revision(early, late, now=NOW)["revision_pct"] is None
    late["consensus"] = 2.2
    late["contributors"] = 1
    assert earnings_consensus_revision(early, late, now=NOW)["revision_pct"] is None
