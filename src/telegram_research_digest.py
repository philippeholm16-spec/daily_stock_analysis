"""Telegram message formatting for RESEARCH WATCHLISTS, never trade signals."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def _safe_line(text, *, width=150):
    return " ".join(str(text).split())[:width]


def format_research_digest(review, *, generated_at=None):
    """Pure function; verified caller has reviewed EVERY candidate."""
    if (not isinstance(review, dict)
            or review.get("mode") != "RESEARCH_ONLY"
            or review.get("actionable_count") != 0
            or review.get("all_checked") is not True):
        raise ValueError("review_required")
    accepted = review.get("accepted")
    if not isinstance(accepted, list):
        raise ValueError("invalid_review")
    generated_at = generated_at or datetime.now(timezone.utc)
    stamp = generated_at.astimezone(ZoneInfo("Europe/Stockholm")).strftime("%Y-%m-%d %H:%M")
    heading = (f"SVENSK BÖRSBEVAKNING | {stamp}\n"
               "RESEARCH – INTE KÖPREKOMMENDATION\n"
               "Nyhetsdrivet urval, INTE hela börsen. Kurser kan vara fördröjda.\n")
    if not accepted:
        return heading + "\nInga kvalificerade bevakningskandidater i denna körning."
    sections = [heading]
    for number, item in enumerate(accepted[:8], 1):
        catalysts = ", ".join(item.get("catalysts", [])) or "Nyhet"
        last = item.get("last_price")
        price = (f"{last:.2f} kr (ej realtidsverifierad)"
                 if isinstance(last, (float, int)) and not isinstance(last, bool) and last > 0
                 else "okänd")
        block = (
            f"\n{number}. {_safe_line(item.get('ticker', '?'), width=25)}"
            f" | bevakningspoäng {item['research_score']}/10\n"
            f"{_safe_line(item['headline'])}\n"
            f"Katalysator: {_safe_line(catalysts, width=70)}\n"
            f"Kurs: {price}\n"
            f"Källa: {_safe_line(item['source'], width=40)}\n"
            f"{item['news_url']}\n"
        )
        if len("".join(sections)) + len(block) > 3800:
            break
        sections.append(block)
    sections.append("\nInga köp-/säljnivåer har godkänts. Kontrollera källor och realtidskurs själv.")
    return "".join(sections)[:4096]
