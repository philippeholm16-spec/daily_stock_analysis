"""Telegram digest: publishers discover; Stock Analyst alone assesses potential.

No source recommendation is included in the decision score. Display levels
only if derived from validated stock price history with net R/R >= 2 and the
1%-of-capital cost gate; they remain indicative, not executable trade signals.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def _short(text, *, width=125):
    return " ".join(str(text or "").split())[:width]


def _levels(analysis):
    if analysis.get("status") != "ANALYZED_INDICATIVE_SETUP":
        return ("Stop-loss (lägsta säljnivå): Ej fastställd\n"
                "Målkurs (sell point): Ej fastställd\n"
                "Potential: Ej fastställd – ingen godkänd teknisk setup\n")
    return (
        f"Stop-loss, preliminär: {analysis['lowest_sell_point']:.2f} kr\n"
        f"Målkurs, preliminär: {analysis['sell_point']:.2f} kr\n"
        f"Potential till målkurs: +{analysis['potential_pct']:.2f} % (ej sannolikhet)\n"
        f"Netto risk/reward: {analysis['net_rr']:.2f}\n"
        f"Risk vid exempelposition: {analysis['max_risk_sek']:.0f} kr "
        f"({analysis['quantity']} aktier; ej order)\n"
    )


def format_research_digest(review, *, generated_at=None):
    """Render independently reviewed Swedish stock research, max 4096 units."""
    if (not isinstance(review, dict)
            or review.get("mode") != "RESEARCH_ONLY"
            or review.get("actionable_count") != 0
            or review.get("all_checked") is not True):
        raise ValueError("review_required")
    rows = review.get("accepted")
    if not isinstance(rows, list):
        raise ValueError("invalid_review")
    generated_at = generated_at or datetime.now(timezone.utc)
    stamp = generated_at.astimezone(ZoneInfo("Europe/Stockholm")).strftime("%Y-%m-%d %H:%M")
    heading = (
        f"STOCK ANALYST | SVENSK AKTIEBEVAKNING | {stamp}\n"
        "Nyheter används BARA för att hitta aktier. Pressens köp-/säljråd "
        "styr INTE Stock Analysts bedömning.\n"
        "PRELIMINÄR RESEARCH, INTE KÖPREKOMMENDATION ELLER HANDELSSIGNAL. Kurser kan vara fördröjda.\n"
        f"Telegramlarm endast vid mycket god teknisk potential enligt Stock Analyst "
        f"(minst {review.get('min_independent_analyst_score', 85):g}/100) "
        "OCH validerade preliminära stopp-/målnivåer.\n"
    )
    if not rows:
        return heading + "\nIngen aktie uppfyller Stock Analysts krav för mycket god potential i denna körning."
    parts = [heading]
    for index, row in enumerate(rows[:8], start=1):
        a = row["stock_analyst"]
        score = (f"{a['score']:.0f}/100 | {_short(a['quality'], width=45)}"
                 if a.get("score") is not None else "Analysunderlag saknas")
        price = row.get("last_price")
        price_text = (f"{price:.2f} kr (ej realtidsverifierad)"
                      if isinstance(price, (int, float)) and price > 0
                      else "Ej tillgänglig")
        reasons = "; ".join(_short(x, width=115) for x in a.get("why", [])[:2]) or "Otillräcklig teknisk evidens"
        risks = "; ".join(_short(x, width=115) for x in a.get("risks", [])[:1]) or "Ingen specifik riskinformation"
        item = (
            f"\n{index}. {_short(row['ticker'], width=20)} "
            f"| Stock Analysts egna bedömning: {score}\n"
            f"Affärspotential: {_short(a.get('potential_quality', 'Ej bedömbar'), width=55)}\n"
            f"Senaste kurs: {price_text}\n"
            f"{_levels(a)}"
            f"VARFÖR: {reasons}\n"
            f"RISK: {risks}\n"
            f"Hittad via: {_short(row['source'], width=35)} (enbart upptäckt)\n"
            f"Nyhet: {_short(row['headline'], width=130)}\n"
            f"{row['news_url']}\n"
        )
        if len(("".join(parts) + item).encode("utf-16-le")) // 2 > 3900:
            break
        parts.append(item)
    parts.append(
        "\nPreliminära nivåer bygger på historiska kurser. Kontrollera "
        "marknadsdata och risk innan handel. Ingen automatisk order."
    )
    result = "".join(parts)
    if len(result.encode("utf-16-le")) // 2 > 4096:
        raise ValueError("digest_too_long")
    return result
