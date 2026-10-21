"""Read one public RSS feed for headline-only discovery, no full-article scraping.

No company identity inference or trading signals. One request, 10-second
timeout, capped bytes, no redirects to other hosts.
"""
import argparse
import json
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit

from src.news_first_discovery import parse_news_feed, classify_catalyst


ALLOWED_FEEDS = {"placera": "https://www.placera.se/artiklar/rss.xml"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_public_feed(url):
    if urlsplit(url).scheme != "https" or url not in ALLOWED_FEEDS.values():
        raise ValueError("feed_not_allowlisted")
    req = Request(url, headers={"User-Agent": "SwedishStockResearchBot/0.1 (read-only RSS research)",
                                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with build_opener(NoRedirect()).open(req, timeout=10) as response:
        payload = response.read(1_000_001)
        if len(payload) > 1_000_000:
            raise ValueError("feed_too_large")
        return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=tuple(ALLOWED_FEEDS), required=True)
    args = parser.parse_args()
    payload = fetch_public_feed(ALLOWED_FEEDS[args.source])
    items, errors = parse_news_feed(payload, source=args.source,
                                    verified_isin_field=False, max_items=40)
    output = {
        "source": args.source,
        "feed": ALLOWED_FEEDS[args.source],
        "parsed": len(items),
        "rejected_entries": len(errors),
        "identity_verified": False,
        "actionable": False,
        "headlines": [
            {"headline": x.headline, "published_at": x.published_at.isoformat(),
             "url": x.url, "catalysts": classify_catalyst(x.headline)}
            for x in items[:20] if x.headline and x.url.startswith("https://")
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
