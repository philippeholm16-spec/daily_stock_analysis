"""Stock Analyst Sweden: independent technical evaluation of XSTO discoveries.

Publisher titles, sentiment, opinions and news priority are NEVER inputs.
Technical bars/quotes must be verified and sufficiently recent. Targets come
only from observed prior highs (resistance), NEVER a fabricated RR multiple.

Preliminary levels do NOT authorize a trade: unofficial Avanza quotes are not
verified real-time, and publisher article matches may be provisional.
"""
from datetime import datetime, timezone
from math import isfinite
from statistics import mean

from src.swedish_market_scanner import Candidate, evaluate


def _positive(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and isfinite(value) and value > 0)


def _timestamp(value):
    """Require Unix milliseconds (not seconds) with timezone-aware datetime."""
    if not isinstance(value, int) or isinstance(value, bool) or not 1_500_000_000_000 <= value <= 4_000_000_000_000:
        raise ValueError("invalid_millisecond_timestamp")
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def validate_chart(raw_chart, *, now, max_bar_age_hours=96):
    """Ensure a single correctly paginated, chronological and recent OHLC page."""
    if not isinstance(raw_chart, dict):
        raise ValueError("missing_chart")
    meta = raw_chart.get("pagination") or {}
    data = raw_chart.get("data") or {}
    resolution = ((data.get("metadata") or {}).get("resolution") or {}).get("chartResolution")
    bars = data.get("ohlc")
    if (not isinstance(bars, list) or len(bars) < 25 or len(bars) > 100
            or resolution not in ("five_minutes", "ten_minutes", "thirty_minutes", "hour", "day")
            or not isinstance(meta.get("total"), int) or meta["total"] < 25
            or meta.get("offset") != meta["total"] - len(bars)
            or meta.get("returned") != len(bars)):
        raise ValueError("incomplete_or_unsupported_chart_page")
    result = []
    previous = None
    for raw in bars:
        if not isinstance(raw, dict):
            raise ValueError("invalid_chart_bar")
        stamp = _timestamp(raw.get("timestamp"))
        price = [raw.get(k) for k in ("open", "high", "low", "close")]
        volume = raw.get("totalVolumeTraded")
        if (not all(_positive(v) for v in price)
                or price[1] < max(price[0], price[3])
                or price[2] > min(price[0], price[3])
                or price[2] > price[1]
                or not isinstance(volume, (int, float)) or isinstance(volume, bool)
                or not isfinite(volume) or volume < 0
                or not float(volume).is_integer()
                or (previous is not None and stamp <= previous)):
            raise ValueError("invalid_or_unsorted_chart_data")
        previous = stamp
        result.append({"at": stamp, "open": float(price[0]),
                       "high": float(price[1]), "low": float(price[2]),
                       "close": float(price[3]), "volume": int(volume)})
    bar_age = (now - result[-1]["at"]).total_seconds() / 3600
    if not 0 <= bar_age <= max_bar_age_hours:
        raise ValueError("stale_or_future_chart")
    return result, resolution


def _decline(reason):
    return {
        "engine": "Stock Analyst Sweden / independent technical v1",
        "status": "ANALYSIS_UNAVAILABLE",
        "score": None, "quality": "Kan inte bedömas",
        "why": [], "risks": [reason],
        "lowest_sell_point": None, "sell_point": None,
        "potential_pct": None, "entry_price": None,
        "net_rr": None, "max_risk_sek": None, "quantity": None,
        "levels_status": "EJ_FASTSTÄLLDA",
        "actionable": False, "data_verified_real_time": False,
        "source_news_opinion_used": False,
    }


def analyze_xsto_candidate(candidate, raw_chart, *, now=None,
                           capital_sek=15000,
                           commission=1.0,
                           spread_per_share=0.02,
                           slippage_per_share_per_side=0.02):
    """Analyze one VERIFIED stock independently of news ratings.

    Always return one result, including failures. A real-time trading
    proposal additionally needs separate issuer identity, coverage and quote
    freshness gates; this function NEVER yields a live trade signal.
    """
    now = now or datetime.now(timezone.utc)
    if (not isinstance(candidate, dict)
            or candidate.get("mic") != "XSTO"
            or candidate.get("identity_source") != "avanza_get_stock_info"
            or not isinstance(candidate.get("isin"), str)
            or len(candidate["isin"]) != 12
            or not isinstance(candidate.get("ticker"), str)
            or not _positive(candidate.get("last_price"))
            or not _positive(capital_sek)):
        return _decline("Aktieidentitet, kapital eller senaste kurs saknas/är fel.")
    try:
        bars, resolution = validate_chart(raw_chart, now=now)
    except (ValueError, TypeError, OverflowError) as exc:
        return _decline("Otillräcklig eller för gammal kursserie: " + str(exc))
    close = bars[-1]["close"]
    price = float(candidate["last_price"])
    if abs(price / close - 1) > 0.12:
        return _decline("Senaste kurs avviker mer än 12 % från senaste verifierade kursstapel.")
    last20 = bars[-20:]
    last5 = bars[-5:]
    ma20 = mean(b["close"] for b in last20)
    mom5 = (close / bars[-6]["close"] - 1) * 100
    old20vol = mean(b["volume"] for b in bars[-21:-1])
    rvol = bars[-1]["volume"] / old20vol if old20vol > 0 else None
    true_ranges = []
    for i in range(len(bars) - 14, len(bars)):
        b, prior = bars[i], bars[i-1]
        true_ranges.append(max(b["high"] - b["low"],
                               abs(b["high"] - prior["close"]),
                               abs(b["low"] - prior["close"])))
    atr = mean(true_ranges)
    previous_high = max(b["high"] for b in bars[-21:-1])
    low5 = min(b["low"] for b in last5)

    # Evidence-backed *research* rating; no opinion scoring or news score.
    reasons, risks = [], []
    points = 0
    if close > ma20:
        points += 30
        reasons.append("Kursen ligger över 20-stapels medelvärde.")
    else:
        risks.append("Kursen ligger inte över 20-stapels medelvärde.")
    if mom5 >= 1:
        points += 25
        reasons.append(f"Fem-stapels momentum är +{mom5:.1f} %.")
    elif mom5 > 0:
        points += 10
        reasons.append(f"Fem-stapels momentum är +{mom5:.1f} %.")
    else:
        risks.append(f"Fem-stapels momentum är {mom5:+.1f} %.")
    if rvol is not None and rvol >= 1.5:
        points += 20
        reasons.append(f"Volymen är {rvol:.1f}× snittet för 20 tidigare staplar.")
    elif rvol is not None and rvol >= 1:
        points += 10
        reasons.append(f"Volymen är {rvol:.1f}× snittet för 20 tidigare staplar.")
    else:
        risks.append("Ingen bekräftad högre volym än det korta historiska snittet.")
    turnover = candidate.get("turnover_proxy_sek")
    if _positive(turnover) and turnover >= 5_000_000:
        points += 15
        reasons.append("Observerad ungefärlig dagsomsättning över 5 Mkr.")
    else:
        risks.append("Omsättningen är låg eller inte verifierad.")
    spread_pct = candidate.get("spread_pct")
    if isinstance(spread_pct, (float, int)) and not isinstance(spread_pct, bool) and isfinite(spread_pct) and 0 <= spread_pct <= 0.25:
        points += 10
    else:
        risks.append("Spreaden är okänd eller relativt bred.")
    score = max(0, min(100, points))
    quality = ("Hög teknisk styrka" if score >= 75 else
               "Måttlig teknisk styrka" if score >= 50 else "Svag teknisk styrka")

    # Observed historical resistance only, never assume a bullish target.
    stop = low5 - 0.15 * atr
    if stop <= 0 or stop >= price or previous_high <= price:
        return {
            **_decline("Ingen prisnivå med observerat stöd/motstånd och giltig riskprofil."),
            "status": "ANALYZED_NO_VALID_SETUP", "score": score,
            "quality": quality, "why": reasons,
            "risks": risks + ["Ingen evidensbaserad köp-/säljplan kan fastställas."],
            "bar_resolution": resolution,
            "momentum_5_bars_pct": round(mom5, 2),
            "relative_volume_vs_prior20": round(rvol, 2) if rvol is not None else None,
            "source_news_opinion_used": False,
        }
    target = previous_high
    try:
        decision = evaluate(
            Candidate(
                isin=candidate["isin"], mic="XSTO", symbol=candidate["ticker"],
                currency="SEK", last_price=price, entry=price, stop=stop,
                target=target, turnover_sek=float(turnover or 0), as_of=now,
                catalyst=False
            ),
            capital_sek=capital_sek, commission_sek_per_side=commission,
            spread_sek_per_share=spread_per_share,
            slippage_sek_per_share_per_side=slippage_per_share_per_side,
            now=now,
        )
    except (ValueError, TypeError, ZeroDivisionError, OverflowError):
        return _decline("Risk- och positionsberäkningen kunde inte valideras.")
    if not decision.eligible:
        return {
            **_decline("Indikativ teknisk plan underkänd: " + ", ".join(decision.reasons)),
            "status": "ANALYZED_NO_VALID_SETUP", "score": score,
            "quality": quality, "why": reasons,
            "risks": risks + ["Risk/reward, prisnivåer eller 1 %-risk uppfylls inte."],
            "bar_resolution": resolution,
            "momentum_5_bars_pct": round(mom5, 2),
            "relative_volume_vs_prior20": round(rvol, 2) if rvol is not None else None,
            "source_news_opinion_used": False,
        }
    return {
        "engine": "Stock Analyst Sweden / independent technical v1",
        "status": "ANALYZED_INDICATIVE_SETUP",
        "score": score, "quality": quality,
        "why": reasons + ["Historiskt observerat motstånd ovanför senaste kurs."],
        "risks": risks + ["Källans realtid och full börstäckning är ännu inte verifierade."],
        "entry_price": round(price, 2),
        "lowest_sell_point": round(stop, 2),  # stop-loss / invalidation
        "sell_point": round(target, 2),  # prior observed resistance
        "potential_pct": round(100 * (target / price - 1), 2),
        "net_rr": round(decision.reward_to_risk, 2),
        "max_risk_sek": round(decision.risk_sek, 2),
        "quantity": decision.quantity,
        "bar_resolution": resolution,
        "momentum_5_bars_pct": round(mom5, 2),
        "relative_volume_vs_prior20": round(rvol, 2) if rvol is not None else None,
        "levels_status": "ENDAST_PRELIMINÄRT_SCENARIO",
        "actionable": False, "data_verified_real_time": False,
        "source_news_opinion_used": False,
    }
