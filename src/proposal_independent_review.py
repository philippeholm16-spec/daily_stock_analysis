"""Independent deterministic review before a research idea can become a proposal.

Two roles are intentionally separate: discovery makes hypotheses; this
gate checks evidence, provenance, freshness, universe and 1% risk. A PASS
means 'ready for human review', NOT automatic trade authorization.
"""
from datetime import datetime, timezone
from dataclasses import dataclass
from math import isfinite

from src.swedish_market_scanner import Candidate, evaluate


@dataclass(frozen=True)
class ReviewResult:
    ready_for_human_review: bool
    reasons: tuple[str, ...]
    quantity: int = 0
    max_loss_sek: float = 0.0
    net_rr: float = 0.0


def _valid_time(value, *, now, max_age_seconds):
    if not isinstance(value, str):
        return False
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    age = (now - stamp).total_seconds() if stamp.tzinfo else -1
    return 0 <= age <= max_age_seconds


def review_proposal(proposal, coverage, *, capital_sek, now=None):
    """Reject unverified, stale, ambiguous, or over-risk trading proposals.

    Required proposal keys: 'instrument', 'market', 'news', 'levels', 'costs'.
    coverage is the dict from complete_market_coverage audit. Source booleans
    are attestations; production must authenticate source provenance upstream.
    """
    now = now or datetime.now(timezone.utc)
    reasons = []
    if not isinstance(proposal, dict):
        return ReviewResult(False, ("invalid_proposal",))
    if (not isinstance(coverage, dict) or coverage.get("complete") is not True
            or coverage.get("source_verified") is not True
            or coverage.get("reference_independent") is not True
            or coverage.get("reference_fresh") is not True):
        reasons.append("incomplete_or_unverified_universe")
    instrument = proposal.get("instrument")
    market = proposal.get("market")
    news = proposal.get("news")
    levels = proposal.get("levels")
    costs = proposal.get("costs")
    if not all(isinstance(x, dict) for x in (instrument, market, news, levels, costs)):
        return ReviewResult(False, tuple(reasons + ["missing_sections"]))
    if (instrument.get("mic") != "XSTO" or instrument.get("currency") != "SEK"
            or not isinstance(instrument.get("isin"), str)
            or len(instrument["isin"]) != 12
            or not isinstance(instrument.get("symbol"), str)
            or not instrument["symbol"].strip()
            or market.get("isin") != instrument["isin"]
            or market.get("symbol") != instrument["symbol"]):
        reasons.append("instrument_identity_mismatch")
    if (market.get("is_real_time") is not True
            or market.get("timestamp_verified") is not True
            or market.get("entitlement_verified") is not True
            or not market.get("source")
            or not _valid_time(market.get("as_of"), now=now, max_age_seconds=90)):
        reasons.append("quote_delayed_unverified_or_stale")
    if (news.get("issuer_isin_verified") is not True
            or news.get("isin") != instrument.get("isin")
            or not news.get("source") or not news.get("url", "").startswith("https://")
            or not _valid_time(news.get("published_at"), now=now,
                               max_age_seconds=86400)):
        reasons.append("news_unverified_or_stale")
    try:
        entry, stop, target, last = (float(levels[x]) for x in
                                      ("entry", "stop", "target", "last_price"))
        turnover = float(market["turnover_sek"])
        commission = float(costs["commission_sek_per_side"])
        spread = float(costs["spread_sek_per_share"])
        slippage = float(costs["slippage_sek_per_share_per_side"])
        if (not all(isfinite(x) for x in (entry, stop, target, last, turnover,
                                          commission, spread, slippage))
                or isinstance(capital_sek, bool)
                or not isinstance(capital_sek, (int, float))
                or not isfinite(capital_sek) or capital_sek <= 0):
            raise ValueError
    except (TypeError, ValueError, KeyError):
        return ReviewResult(False, tuple(reasons + ["invalid_risk_inputs"]))
    if not (isinstance(instrument.get("isin"), str) and
            isinstance(instrument.get("symbol"), str)):
        return ReviewResult(False, tuple(reasons + ["invalid_instrument_fields"]))
    if not _valid_time(market.get("as_of"), now=now, max_age_seconds=90):
        reasons.append("no_valid_trade_timestamp")
        return ReviewResult(False, tuple(dict.fromkeys(reasons)))
    stamp = datetime.fromisoformat(market["as_of"].replace("Z", "+00:00"))
    quote_price = market.get("last_price")
    if (isinstance(quote_price, bool) or not isinstance(quote_price, (int, float))
            or not isfinite(quote_price) or quote_price <= 0
            or abs(quote_price - last) > max(0.001, quote_price * 0.0001)):
        reasons.append("quote_price_mismatch")
    try:
        candidate = Candidate(
            isin=instrument["isin"], mic=instrument["mic"],
            symbol=instrument["symbol"], currency=instrument["currency"],
            last_price=last, entry=entry, stop=stop, target=target,
            turnover_sek=turnover, as_of=stamp,
            catalyst=True
        )
        decision = evaluate(candidate, capital_sek=capital_sek,
                            commission_sek_per_side=commission,
                            spread_sek_per_share=spread,
                            slippage_sek_per_share_per_side=slippage,
                            max_age_seconds=90, now=now)
    except (KeyError, TypeError, ValueError):
        return ReviewResult(False, tuple(dict.fromkeys(reasons + ["invalid_candidate"])))
    reasons.extend(decision.reasons)
    return ReviewResult(
        ready_for_human_review=not reasons,
        reasons=tuple(dict.fromkeys(reasons)),
        quantity=decision.quantity if not reasons else 0,
        max_loss_sek=decision.risk_sek if not reasons else 0,
        net_rr=decision.reward_to_risk if not reasons else 0,
    )
