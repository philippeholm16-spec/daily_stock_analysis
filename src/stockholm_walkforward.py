"""Conservative historical replay for the independent Swedish technical model.

No future candles enter feature/stop/target calculations. This is a research
backtest, NOT proof of forward predictive accuracy or executable profitability:
fills, exchange latency and quote entitlements are not modeled fully.
"""
from dataclasses import dataclass, asdict
from datetime import timezone
from statistics import mean

from src.stockholm_stock_analyst import analyze_xsto_candidate


@dataclass(frozen=True)
class ReplayTrade:
    observed_at: str
    stop: float
    target: float
    entry: float
    proposed_entry: float
    quantity: int
    outcome: str
    exit_price: float
    r_multiple: float


def simulate_exit(analysis, future_bars, *, commission=1.0,
                  spread=0.02, slippage_per_side=0.02,
                  capital_sek=None, max_entry_gap_pct=0.5):
    """Resolve actual first touch conservatively, including same-bar ambiguity.

    Decisions are made on the prior close, then entry is attempted at NEXT
    bar's opening price. Large opening gaps and cash/risk violations cancel
    the entry (not fictitious fills). Later stop gaps fill at the observed
    opening price. A gap above target never assumes better than target.
    Same-bar stop and target count as stop. Time exits mark to market.
    """
    if not future_bars or analysis.get("status") != "ANALYZED_INDICATIVE_SETUP":
        raise ValueError("invalid_replay_input")
    entry = float(analysis["entry_price"])
    stop = float(analysis["lowest_sell_point"])
    target = float(analysis["sell_point"])
    quantity = analysis["quantity"]
    max_risk = float(analysis["max_risk_sek"])
    if not (0 < stop < entry < target and max_risk > 0
            and isinstance(quantity, int) and quantity > 0):
        raise ValueError("invalid_replay_levels")

    if not 0 <= max_entry_gap_pct <= 5:
        raise ValueError("invalid_entry_gap_limit")
    entry_fill = float(future_bars[0]["open"])
    if (entry_fill <= stop or entry_fill >= target
            or abs(entry_fill / entry - 1) * 100 > max_entry_gap_pct):
        return {
            "outcome": "ENTRY_NOT_FILLED",
            "exit_price": None, "entry_fill_price": None,
            "net_pnl_sek": None, "r_multiple": None,
        }
    cost = quantity * (spread + 2 * slippage_per_side) + 2 * commission
    actual_risk = quantity * (entry_fill - stop) + cost
    permitted_risk = max_risk if capital_sek is None else capital_sek * 0.01
    if actual_risk <= 0 or actual_risk > permitted_risk + 1e-6:
        return {
            "outcome": "RISK_REJECTED_AT_ENTRY",
            "exit_price": None, "entry_fill_price": None,
            "net_pnl_sek": None, "r_multiple": None,
        }
    outcome = "TIME_EXIT"
    exit_price = float(future_bars[-1]["close"])
    for bar in future_bars:
        # Stop gaps after the first bar can lose >1 R despite planned sizing.
        if bar["open"] <= stop:
            outcome, exit_price = "STOP_GAP", float(bar["open"])
            break
        if bar["low"] <= stop and bar["high"] >= target:
            outcome, exit_price = "STOP_AMBIGUOUS", stop
            break
        if bar["low"] <= stop:
            outcome, exit_price = "STOP", stop
            break
        if bar["high"] >= target:
            outcome, exit_price = "TARGET", target
            break
    pnl = quantity * (exit_price - entry_fill) - cost
    return {
        "outcome": outcome,
        "exit_price": round(exit_price, 4),
        "entry_fill_price": round(entry_fill, 4),
        "net_pnl_sek": round(pnl, 2),
        "r_multiple": round(pnl / actual_risk, 4),
    }


def analyze_at(bars, end, *, isin, ticker, capital_sek=15000,
               spread_pct=0.10, commission=1.0,
               per_share_spread=0.02, slippage=0.02,
               window=50):
    """Analyze precisely the first 'end' candles, never bars[end:]."""
    history = bars[max(0, end-window):end]
    if len(history) < 25:
        raise ValueError("insufficient_training_candles")
    snapshot = history[-1]
    now = snapshot["at"]
    # Unentitled historical replay only; not a realtime quote.
    raw = {
        "data": {"ohlc": [
            {"timestamp": int(b["at"].timestamp() * 1000),
             "open": b["open"], "high": b["high"], "low": b["low"],
             "close": b["close"], "totalVolumeTraded": b["volume"]}
            for b in history
        ], "metadata": {"resolution": {"chartResolution": "ten_minutes"}}},
        "pagination": {"total": len(history), "offset": 0, "returned": len(history)},
    }
    entry = snapshot["close"]
    evidence = {
        "mic": "XSTO", "isin": isin, "ticker": ticker,
        "identity_source": "avanza_get_stock_info",
        "last_price": entry,
        "turnover_proxy_sek": entry * sum(b["volume"] for b in history),
        "spread_pct": spread_pct,
    }
    return analyze_xsto_candidate(
        evidence, raw, now=now, capital_sek=capital_sek,
        commission=commission, spread_per_share=per_share_spread,
        slippage_per_share_per_side=slippage
    )


def walk_forward_replay(bars, *, isin, ticker, capital_sek=15000,
                        lookback=50, horizon=12, step=12,
                        spread_pct=0.10, commission=1.0,
                        per_share_spread=0.02, slippage=0.02):
    """Non-overlapping evaluation windows with no information leakage.

    Historical candles supplied must be sorted with timezone-aware dates.
    Only VERY_GOOD opportunities become simulated trades. There is no
    optimization of parameters against the supplied historical outcomes.
    """
    if not 25 <= lookback <= 100 or horizon < 1 or step < horizon:
        raise ValueError("invalid_replay_window")
    if not isinstance(bars, list) or len(bars) < lookback + horizon:
        raise ValueError("insufficient_replay_data")
    for i, bar in enumerate(bars):
        if (bar["at"].tzinfo is None
                or i and bar["at"] <= bars[i-1]["at"]):
            raise ValueError("unsorted_or_naive_replay_timestamps")
    results = []
    skipped_entries = 0
    very_good_opportunities = 0
    windows = 0
    evaluated = 0
    for end in range(lookback, len(bars) - horizon + 1, step):
        windows += 1
        analysis = analyze_at(
            bars, end, isin=isin, ticker=ticker, capital_sek=capital_sek,
            spread_pct=spread_pct, commission=commission,
            per_share_spread=per_share_spread, slippage=slippage,
            window=lookback
        )
        if analysis["status"] != "ANALYSIS_UNAVAILABLE":
            evaluated += 1
        if analysis.get("opportunity_grade") != "VERY_GOOD":
            continue
        very_good_opportunities += 1
        closed = simulate_exit(
            analysis, bars[end:end+horizon], commission=commission,
            spread=per_share_spread, slippage_per_side=slippage,
            capital_sek=capital_sek
        )
        if closed["entry_fill_price"] is None:
            skipped_entries += 1
            continue
        results.append(ReplayTrade(
            observed_at=bars[end-1]["at"].isoformat(),
            stop=analysis["lowest_sell_point"],
            target=analysis["sell_point"],
            entry=closed["entry_fill_price"],
            proposed_entry=analysis["entry_price"],
            quantity=analysis["quantity"],
            outcome=closed["outcome"],
            exit_price=closed["exit_price"],
            r_multiple=closed["r_multiple"]
        ))
    winners = sum(t.r_multiple > 0 for t in results)
    losers = sum(t.r_multiple < 0 for t in results)
    positive = sum(t.r_multiple for t in results if t.r_multiple > 0)
    negative = -sum(t.r_multiple for t in results if t.r_multiple < 0)
    equity, peak, drawdown = 0.0, 0.0, 0.0
    for trade in results:
        equity += trade.r_multiple
        peak = max(peak, equity)
        drawdown = max(drawdown, peak-equity)
    return {
        "ticker": ticker, "isin": isin,
        "historical_candles": len(bars),
        "windows": windows, "evaluated": evaluated,
        "very_good_signals": very_good_opportunities,
        "filled_trades": len(results),
        "skipped_entries": skipped_entries,
        "wins": winners, "losses": losers,
        "win_rate_filled_trades": round(winners/len(results), 4) if results else None,
        "win_rate_all_trades": round(winners/len(results), 4) if results else None,
        "average_r": round(mean(t.r_multiple for t in results), 4)
                     if results else None,
        "profit_factor_r": round(positive / negative, 4) if negative else None,
        "max_drawdown_r": round(drawdown, 4),
        "trades": [asdict(trade) for trade in results],
        "scope": "historical_nonrealtime_replay_not_forward_validated",
        "performance_verified": False,
        "trading_enabled": False,
    }
