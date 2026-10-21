"""Public Google News RSS discovery focused on Swedish financial publishers.

This is a bounded headline index, NOT Google Search API access, a licensed
publisher feed, or a right to scrape paywalled articles. Google News RSS is
not an officially documented stable Google API; failures degrade gracefully.
"""
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit
from urllib.request import build_opener, Request
from scripts.public_rss_probe import NoRedirect
from src.news_first_discovery import parse_news_feed

# Publisher restrictions define which news searches are attempted.
PUBLISHER_GROUPS = {
    "financial_press": ("di.se", "placera.se", "affarsvarlden.se", "borsvarlden.com"),
    "analysis": ("efn.se", "realtid.se", "aktiespararna.se", "privataaffarer.se"),
    "company_releases": ("mfn.se", "cision.se"),
}
GOOGLE_NEWS_HOST = "news.google.com"
CATALYST_QUERY = '(rapport OR vinstvarning OR stororder OR uppköp OR emission) when:1d'


def build_google_news_queries():
    """Return exactly three explicitly scoped Swedish-edition RSS URLs."""
    feeds = {}
    for group, domains in PUBLISHER_GROUPS.items():
        sites = " OR ".join("site:" + d for d in domains)
        query = f"({sites}) {CATALYST_QUERY}"
        feeds[group] = "https://news.google.com/rss/search?" + urlencode({
            "q": query, "hl": "sv", "gl": "SE", "ceid": "SE:sv"
        })
    return feeds


def fetch_google_news(url, *, max_bytes=500_000):
    if url not in build_google_news_queries().values():
        raise ValueError("unapproved_google_news_query")
    if urlsplit(url).hostname != GOOGLE_NEWS_HOST:
        raise ValueError("unapproved_google_news_host")
    req = Request(url, headers={
        "User-Agent": "StockholmMarketResearch/0.1 (+read-only RSS discovery)",
        "Accept": "application/rss+xml, application/xml, text/xml",
    })
    with build_opener(NoRedirect()).open(req, timeout=10) as response:
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError("google_news_feed_too_large")
        return body


def collect_google_news(*, now=None, fetcher=fetch_google_news, max_age_hours=24):
    now = now or datetime.now(timezone.utc)
    entries, errors, by_group = [], [], {}
    seen = set()
    for group, url in build_google_news_queries().items():
        try:
            raw = fetcher(url)
            found, rejected = parse_news_feed(raw, source=f"Google News:{group}",
                                              verified_isin_field=False, max_items=50)
            count = 0
            for item in found:
                age = (now - item.published_at).total_seconds() / 3600
                if age < 0 or age > max_age_hours:
                    continue
                # Never treat Google aggregator links as a publisher-verified ISIN.
                if not item.url.startswith("https://news.google.com/"):
                    continue
                key = (item.headline.casefold().strip(), item.published_at.isoformat())
                if key in seen:
                    continue
                seen.add(key)
                entries.append(item)
                count += 1
            by_group[group] = count
            errors.extend([f"{group}:invalid_item"] * len(rejected))
        except Exception as exc:
            errors.append(f"{group}:{type(exc).__name__}")
            by_group[group] = 0
    return {"news_items": entries, "errors": errors, "groups": by_group,
            "verified_issuer_attribution": False, "actionable": False}
