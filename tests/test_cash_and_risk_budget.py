"""Capital allocation edge cases for the offline, risk-capped evaluator."""
from datetime import datetime, timezone

from src.swedish_market_scanner import Candidate, evaluate


NOW = datetime(2026, 10, 21, 9, tzinfo=timezone.utc)


def candidate(**kwargs):
    data = dict(isin="SE0000000000", symbol="EXAMPLE", mic="XSTO",
                currency="SEK", last_price=600.0, entry=600.0, stop=599.0,
                target=606.0, turnover_sek=20_000_000.0, as_of=NOW)
    data.update(kwargs)
    return Candidate(**data)


def test_high_price_position_is_capped_by_cash_not_rejected():
    d = evaluate(candidate(), capital_sek=10_000, now=NOW)
    assert d.eligible
    assert d.quantity == 16
    assert d.risk_sek <= 100
    assert d.reward_to_risk >= 2
    assert d.quantity * (600 + 0.01 + 0.02) + 1 <= 10_000


def test_cash_gate_accounts_for_entry_costs():
    d = evaluate(candidate(entry=10_000, last_price=10_000,
                           stop=9_995, target=10_020),
                 capital_sek=10_000, now=NOW)
    assert not d.eligible
    assert "insufficient_cash" in d.reasons


def test_commission_reduces_affordable_quantity():
    d = evaluate(candidate(entry=1000, last_price=1000,
                           stop=999, target=1006),
                 capital_sek=10_000, commission_sek_per_side=25,
                 now=NOW)
    assert d.eligible
    assert d.quantity == 9
    assert d.risk_sek <= 100


def test_never_exceeds_one_percent_across_capital_range():
    for capital in [10_000, 15_000, 25_000]:
        d = evaluate(candidate(entry=240, last_price=240,
                               stop=238, target=250),
                     capital_sek=capital,
                     commission_sek_per_side=7,
                     spread_sek_per_share=0.2,
                     slippage_sek_per_share_per_side=0.2,
                     now=NOW)
        assert d.eligible
        assert d.risk_sek <= capital * 0.01
        assert d.quantity * (240 + 0.1 + 0.2) + 7 <= capital
