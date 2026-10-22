"""Regression: Pareto Bank IS NOT Pareto Securities' Elekta target."""
import json
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone
import pytest

from src.analyst_target_history import inspect_target_path

NOW = datetime(2026, 10, 22, 12, 40, tzinfo=timezone.utc)


def subjects():
    return json.loads(Path(
        "data/pareto_company_broker_disambiguation_2026_10.json"
    ).read_text(encoding="utf-8"))["studies"]


def score(record, **kwargs):
    return inspect_target_path(
        record["events"], isin=record["isin"], mic=record["mic"],
        symbol=record["symbol"], issuer=record["issuer"],
        currency=record["currency"], now=NOW, **kwargs
    )


def test_elekta_latest_raise_but_full_six_month_target_path_negative():
    elekta = subjects()[0]
    out = score(elekta)
    assert out["identity"]["analyst_house"] == "Pareto Securities"
    assert out["identity"]["isin"] == "SE0000163628"
    assert out["latest_revision"]["old"] == 65
    assert out["latest_revision"]["new"] == 68
    assert out["latest_revision"]["change_pct"] == 4.62
    assert out["time_windows_days"]["30"]["direction"] == "NO_OBSERVED_CHANGE"
    assert out["time_windows_days"]["90"]["change_pct"] == 4.62
    assert out["time_windows_days"]["180"]["change_pct"] == -2.86
    assert out["eps_consensus_momentum"] == "NOT_DERIVED_FROM_TARGET_CHANGES"
    assert out["actionable"] is False


def test_pareto_bank_carnegie_cut_is_negative_not_elekta_broker_signal():
    bank = subjects()[1]
    out = score(bank)
    assert out["identity"]["isin"] == "NO0010397581"
    assert out["identity"]["mic"] == "XOSL"
    assert out["identity"]["analyst_house"] == "DNB Carnegie"
    assert out["time_windows_days"]["30"]["change_pct"] == -16.67
    assert out["time_windows_days"]["90"]["direction"] == "DOWN"
    assert bank["specific_broker_eps_revision_pct"] == {
        "2026": -18, "2027": -13
    }
    assert bank["eps_not_market_consensus"] is True


def test_loan_loss_bank_revision_never_contaminates_elekta_target_history():
    bank = subjects()[1]
    ekta = subjects()[0]
    with pytest.raises(ValueError, match="different_stock_broker"):
        inspect_target_path(
            [ekta["events"][0], bank["events"][0]],
            isin=ekta["isin"], mic=ekta["mic"], symbol=ekta["symbol"],
            issuer=ekta["issuer"], currency=ekta["currency"], now=NOW
        )


def test_same_analyst_old_and_new_must_form_consistent_chain():
    ekta = deepcopy(subjects()[0])
    ekta["events"][1]["old"] = 80
    with pytest.raises(ValueError, match="inconsistent"):
        score(ekta)


def test_morningstar_value_model_cannot_be_counted_as_price_target():
    ele = deepcopy(subjects()[0])
    ele["events"][1]["kind"] = "MODEL_FAIR_VALUE"
    with pytest.raises(ValueError, match="fair_value_or_other"):
        score(ele)


def test_missing_source_is_not_an_observed_analyst_revision():
    ele = deepcopy(subjects()[0])
    ele["events"][0]["source"] = None
    with pytest.raises(ValueError, match="unverified_target"):
        score(ele)


def test_future_revision_is_not_used():
    bank = deepcopy(subjects()[1])
    bank["events"][0]["at"] = "2026-10-24T11:00:00+02:00"
    with pytest.raises(ValueError, match="outside_available"):
        score(bank)


def test_no_observations_is_unknown_not_false_zero_momentum():
    bank = deepcopy(subjects()[1])
    bank["events"] = []
    output = score(bank)
    assert output["latest_revision"] is None
    assert output["time_windows_days"]["180"]["change_pct"] is None


def test_duplicate_conflicting_same_day_cannot_bias_revisions():
    bank = deepcopy(subjects()[1])
    bank["events"].append({**bank["events"][0], "new": 45})
    with pytest.raises(ValueError, match="duplicate"):
        score(bank)
