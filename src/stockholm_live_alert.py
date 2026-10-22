"""Final read-only live-alert composition for independently assessed Swedish stocks.

This function formats evidence; it DOES NOT send notifications or orders.
Caller must derive QuoteGateResult in-process from licensed, authenticated
IBKR callbacks. Delayed/public Avanza prices cannot be substituted.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.stockholm_realtime_entry_recheck import reprice_with_live_quote


def _words(value, maximum=190):
    return " ".join(str(value or "").split())[:maximum]


def build_live_alert(instrument, stock_analyst, quality_result, *,
                     now=None, capital_sek=15000):
    """Return a Swedish Telegram preview only when all independent gates pass.

    Even a passing alert is RESEARCH for manual Avanza execution; not a
    trading authorization or validation of strategy profitability.
    """
    now = now or datetime.now(timezone.utc)
    if not isinstance(instrument, dict) or not isinstance(stock_analyst, dict):
        return {"ready_for_preview": False, "reason": "missing_instrument_or_analysis"}
    isin, symbol = instrument.get("isin"), instrument.get("symbol")
    if (not isinstance(isin, str) or len(isin) != 12 or not isinstance(symbol, str)
            or not symbol.strip() or instrument.get("mic") != "XSTO"
            or stock_analyst.get("source_news_opinion_used") is not False):
        return {"ready_for_preview": False, "reason": "identity_or_analysis_not_verified"}
    if (not isinstance(stock_analyst.get("why"), list)
            or len(stock_analyst["why"]) < 2
            or not isinstance(stock_analyst.get("risks"), list)):
        return {"ready_for_preview": False, "reason": "insufficient_independent_rationale"}
    result = reprice_with_live_quote(
        stock_analyst, quality_result, isin=isin, symbol=symbol,
        capital_sek=capital_sek, now=now
    )
    if result["status"] != "LIVE_QUOTE_REPRICED_FOR_HUMAN_RESEARCH":
        return {"ready_for_preview": False, "reason": result["reasons"][0]}
    p = result["levels"]
    quote = quality_result.quote
    # Hard separation from trading: only plain text, without a command or
    # a clickable broker order URL, is produced.
    observed_at = datetime.fromisoformat(quote["as_of"]).astimezone(
        ZoneInfo("Europe/Stockholm")
    ).strftime("%Y-%m-%d %H:%M:%S")
    rationale = "; ".join(_words(s, maximum=100) for s in stock_analyst["why"][:3])
    risk_text = "; ".join(_words(s, maximum=110)
                          for s in stock_analyst["risks"][:2])
    message = (
        f"STOCK ANALYST | MYCKET GOD PRELIMINÄR POTENTIAL\n"
        f"{_words(symbol, maximum=30)} | {stock_analyst['score']:.0f}/100\n"
        f"Nasdaq Stockholm realtidskontroll: {observed_at}\n"
        f"Verifierad källa: IBKR Nordic L1, Nasdaq Stockholm (XSTO)\n"
        f"Indikativ köp/ask: {p['entry_ask']:.2f} kr\n"
        f"Lägsta säljnivå / stop-loss: {p['stop_loss']:.2f} kr\n"
        f"Målkurs / sell point: {p['target']:.2f} kr\n"
        f"Potential till målkurs: +{p['potential_pct']:.2f}%\n"
        f"Risk/reward netto: {p['net_rr']:.2f}\n"
        f"Exempelposition: {p['quantity']} aktier, beräknad risk {p['risk_sek']:.0f} kr\n"
        f"VARFÖR: {rationale}\n"
        f"RISKER: {risk_text}\n"
        f"Ingen garanti, ingen order. Manuell kontroll i Avanza krävs."
    )
    if len(message.encode("utf-16-le")) // 2 > 4096:
        return {"ready_for_preview": False, "reason": "message_too_long"}
    return {
        "ready_for_preview": True,
        "status": "READ_ONLY_RESEARCH_PREVIEW",
        "data_quality": quote["data_quality"],
        "isin": isin,
        "message": message,
        "prepared_at": now.isoformat(),
        "auto_order_enabled": False,
    }
