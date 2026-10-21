"""News-first candidate discovery from explicitly supplied RSS/Atom XML.

No scraping, network access, credentials or implicit company matching.
Only a source that publishes a validated ISIN in a dedicated field may mark
the instrument verified. Headlines are never treated as identity evidence.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re
import xml.etree.ElementTree as ET

from src.swedish_stock_news import NewsItem, link_news

ISIN_RE = re.compile(r"^SE[A-Z0-9]{10}$")
EVENT_WORDS = {
    "report": ("rapport", "interim report", "quarterly", "bokslut"),
    "guidance": ("vinstvarning", "profit warning", "prognos", "guidance"),
    "order": ("stororder", "major order", "order värd", "order worth"),
    "corporate_action": ("uppköp", "takeover", "förvärv", "acquisition"),
    "financing": ("nyemission", "rights issue", "finansiering"),
}


def _local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element, name):
    for child in element:
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _parse_date(value):
    if not value:
        raise ValueError("missing_publication_date")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        dt = parsedate_to_datetime(value)
    if dt.tzinfo is None:
        raise ValueError("naive_publication_date")
    return dt.astimezone(timezone.utc)


def parse_news_feed(xml, *, source, verified_isin_field=False, max_items=100):
    """Parse feed bytes without fetching; no trust in headline ticker mentions.

    verified_isin_field must be explicitly enabled for a trusted source
    contract that supplies <isin>SE...</isin> as an instrument identifier.
    """
    if not source or max_items < 1 or len(xml) > 2_000_000:
        raise ValueError("invalid_feed_input")
    root = ET.fromstring(xml)
    entries = [e for e in root.iter() if _local(e.tag) in ("item", "entry")][:max_items]
    output, rejected = [], []
    for entry in entries:
        try:
            headline = _child_text(entry, "title")
            url = _child_text(entry, "link")
            if not url:
                for child in entry:
                    if _local(child.tag) == "link":
                        url = child.attrib.get("href", "")
                        if url:
                            break
            published = _parse_date(_child_text(entry, "pubdate") or
                                    _child_text(entry, "published") or
                                    _child_text(entry, "updated"))
            isin = _child_text(entry, "isin")
            if not ISIN_RE.fullmatch(isin):
                isin = None
            output.append(NewsItem(source=source, url=url, headline=headline,
                                   published_at=published, isin=isin, symbol=None,
                                   verified_instrument=bool(verified_isin_field and isin)))
        except (ValueError, TypeError, OverflowError):
            rejected.append("invalid_feed_entry")
    return output, rejected


def classify_catalyst(headline):
    """Keyword triage, not AI sentiment, probability or a trade signal."""
    h = headline.casefold()
    return tuple(name for name, words in EVENT_WORDS.items()
                 if any(word in h for word in words))


def discover_news_candidates(xml, *, source, instruments, now=None,
                             verified_isin_field=False):
    news, parse_errors = parse_news_feed(xml, source=source,
                                        verified_isin_field=verified_isin_field)
    linked, excluded = link_news(news, instruments, now=now)
    candidates = [{"isin": instrument["isin"], "symbol": instrument["symbol"],
                   "headline": item.headline, "source": item.source,
                   "url": item.url, "published_at": item.published_at.isoformat(),
                   "catalysts": classify_catalyst(item.headline),
                   "actionable": False}
                  for instrument, item in linked]
    return {"candidates": candidates, "unlinked": len(excluded),
            "parse_errors": len(parse_errors), "parsed": len(news)}
