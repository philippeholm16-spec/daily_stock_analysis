from datetime import datetime, timedelta, timezone

from src.swedish_market_scanner import Candidate, evaluate


NOW = datetime(2026, 10, 21, 9, 0, tzinfo=timezone.utc)


def sample(**overrides):
    data = dict(isin="SE0000000000", mic="XSTO", symbol="TEST-A",
                currency="SEK", last_price=100, entry=100, stop=98,
                target=106, turnover_sek=1_000_000, as_of=NOW)
    data.update(overrides)
    return Candidate(**data)


def test_valid_candidate():
    d = evaluate(sample(), capital_sek=10000, now=NOW)
    assert d.eligible and d.quantity > 0 and d.risk_sek <= 100 and d.reward_to_risk >= 2


def test_stale_quote_rejected():
    d = evaluate(sample(as_of=NOW - timedelta(minutes=16)), capital_sek=10000, now=NOW)
    assert not d.eligible and "stale_or_future_quote" in d.reasons


def test_naive_timestamp_rejected():
    assert not evaluate(sample(as_of=NOW.replace(tzinfo=None)), capital_sek=10000, now=NOW).eligible


def test_wrong_exchange_rejected():
    assert not evaluate(sample(mic="XHEL"), capital_sek=10000, now=NOW).eligible


def test_invalid_levels_rejected():
    assert not evaluate(sample(stop=101), capital_sek=10000, now=NOW).eligible


def test_low_reward_to_risk_rejected():
    d = evaluate(sample(target=102), capital_sek=10000, now=NOW)
    assert not d.eligible and "reward_to_risk_below_two" in d.reasons


def test_costs_and_risk_budget():
    d = evaluate(sample(target=108), capital_sek=25000, commission_sek_per_side=10,
                 spread_sek_per_share=0.2, slippage_sek_per_share_per_side=0.2, now=NOW)
    assert d.eligible and d.risk_sek <= 250


def test_missing_quote_rejected():
    assert not evaluate(sample(last_price=float("nan")), capital_sek=10000, now=NOW).eligible


def test_no_overspending():
    d = evaluate(sample(entry=10000, last_price=10000, stop=9990, target=10040),
                 capital_sek=10000, now=NOW)
    assert not d.eligible and "insufficient_cash" in d.reasons
