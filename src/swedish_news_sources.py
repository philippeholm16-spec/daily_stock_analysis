"""Publisher inventory for Swedish-market catalyst research.

Registry != a live integration or a license to scrape. All sources default to
disabled; enable individually only after confirming technical and usage rights.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class NewsSource:
    name: str
    homepage: str
    category: str
    access: str
    priority: int
    enabled: bool = False
    feed_url: str | None = None


SOURCES = (
    NewsSource("Dagens industri", "https://www.di.se", "financial_press", "rights_review_required", 1),
    NewsSource("Nyhetsbyran Direkt", "https://www.direkt.se", "news_agency", "license_required", 1),
    NewsSource("Placera", "https://www.placera.se", "financial_press", "feed_and_terms_review_required", 1),
    NewsSource("Affarsvarlden", "https://www.affarsvarlden.se", "financial_press", "rights_review_required", 2),
    NewsSource("Borsvarlden", "https://www.borsvarlden.com", "financial_press", "rights_review_required", 2),
    NewsSource("Aktiespararna", "https://www.aktiespararna.se", "financial_press", "rights_review_required", 2),
    NewsSource("Privata Affarer", "https://www.privataaffarer.se", "financial_press", "rights_review_required", 3),
    NewsSource("Realtid", "https://www.realtid.se", "financial_press", "rights_review_required", 3),
    NewsSource("Dagens PS", "https://www.dagensps.se", "financial_press", "rights_review_required", 3),
    NewsSource("EFN", "https://efn.se", "financial_press", "rights_review_required", 2),
    NewsSource("Finwire", "https://www.finwire.com", "news_agency", "license_required", 1),
    NewsSource("Redeye", "https://www.redeye.se", "equity_research", "rights_review_required", 2),
    NewsSource("Borsveckan", "https://www.borsveckan.se", "equity_research", "rights_review_required", 3),
    NewsSource("Nasdaq Nordic", "https://www.nasdaq.com/solutions/nasdaq-nordic", "regulatory", "feed_and_terms_review_required", 1),
    NewsSource("MFN", "https://mfn.se", "company_releases", "feed_and_terms_review_required", 1),
    NewsSource("Cision", "https://www.cision.se", "company_releases", "feed_and_terms_review_required", 2),
    NewsSource("Riksbanken", "https://www.riksbank.se", "macro", "public_rss_review_terms", 2,
               feed_url="https://www.riksbank.se/sv/rss/pressmeddelanden/"),
)


def enabled_sources():
    return tuple(source for source in SOURCES if source.enabled)


def source_summary():
    return {"catalogued": len(SOURCES), "enabled": len(enabled_sources()),
            "pending_review": sum(not s.enabled for s in SOURCES)}
