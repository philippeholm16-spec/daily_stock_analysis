"""Independent proposal-review tests with hypothetical evidence only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from src.proposal_independent_review import review_proposal

NOW = datetime(2026, 10, 21, 9, tzinfo=timezone.utc)
ISIN = "SE0000115446"


def fixture():
    coverage = {"complete": True, "source_verified": True,
                "reference_independent": True, "reference_fresh": True}
    payload = {
        "instrument": {"isin": ISIN, "symbol": "VOLV B", "mic": "XSTO", "currency": "SEK"},
        "market": {"isin": ISIN, "symbol": "VOLV B", "last_price": 100.0,
                   "source": "hypothetical-authorized-provider",
                   "is_real_time": True, "timestamp_verified": True,
                   "entitlement_verified": True, "as_of": NOW.isoformat(),
                   "turnover_sek": 10_000_000},
        "news": {"isin": ISIN, "issuer_isin_verified": True, "source": "fixture",
                 "url": "https://example.org/issuer", "published_at": NOW.isoformat()},
        "levels": {"entry": 100, "stop": 98, "target": 106, "last_price": 100},
        "costs": {"commission_sek_per_side": 1, "spread_sek_per_share": 0.02,
                  "slippage_sek_per_share_per_side": 0.02},
    }
    return payload, coverage


def test_fully_verified_fixture_only_ready_for_human_review():
    proposal, cov = fixture()
    result = review_proposal(proposal, cov, capital_sek=10_000, now=NOW)
    assert result.ready_for_human_review
    assert result.quantity > 0 and result.net_rr >= 2
    assert result.max_loss_sek <= 100


def test_current_delayed_avanza_data_rejected():
    proposal, cov = fixture()
    proposal["market"]["is_real_time"] = False
    result = review_proposal(proposal, cov, capital_sek=10_000, now=NOW)
    assert not result.ready_for_human_review
    assert "quote_delayed_unverified_or_stale" in result.reasons


def test_unverified_complete_market_rejected():
    proposal, cov = fixture()
    cov["complete"] = False
    assert not review_proposal(proposal, cov, capital_sek=10_000, now=NOW).ready_for_human_review


def test_stale_quotes_rejected():
    proposal, cov = fixture()
    proposal["market"]["as_of"] = (NOW - timedelta(minutes=16)).isoformat()
    result = review_proposal(proposal, cov, capital_sek=10_000, now=NOW)
    assert not result.ready_for_human_review
    assert "quote_delayed_unverified_or_stale" in result.reasons


def test_news_requires_verified_isin():
    proposal, cov = fixture()
    proposal["news"]["issuer_isin_verified"] = False
    assert not review_proposal(proposal, cov, capital_sek=10_000, now=NOW).ready_for_human_review


def test_wrong_stock_quote_is_rejected():
    proposal, cov = fixture()
    proposal["market"]["isin"] = "SE0021628898"
    result = review_proposal(proposal, cov, capital_sek=10_000, now=NOW)
    assert not result.ready_for_human_review
    assert "instrument_identity_mismatch" in result.reasons


def test_costs_reduce_net_reward_below_two():
    proposal, cov = fixture()
    proposal["levels"]["target"] = 102
    result = review_proposal(proposal, cov, capital_sek=10_000, now=NOW)
    assert not result.ready_for_human_review
    assert "reward_to_risk_below_two" in result.reasons


def test_mismatched_quote_price_rejected():
    proposal, cov = fixture()
    proposal["market"]["last_price"] = 103.0
    assert not review_proposal(proposal, cov, capital_sek=10_000, now=NOW).ready_for_human_review


def test_missing_sections_do_not_crash():
    assert not review_proposal({}, {}, capital_sek=10_000, now=NOW).ready_for_human_review
