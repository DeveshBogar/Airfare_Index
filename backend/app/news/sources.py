"""Real-world news sources for the airfare-drivers feed (app.news.fetch_news).

Each entry is a real, publicly published RSS feed — not a guessed or
invented URL. Every one was fetched and inspected by hand before being
added here, and every path is checked against that domain's live
robots.txt at request time via the same ComplianceGate class the price
scrapers use (app.scraper.compliance) — the same fail-closed, no-live-
robots.txt-no-fetch policy applies here as it does to fare data.

Google News' own RSS search feed was deliberately NOT used: its response
carries a copyright notice restricting the feed to "personal, non-
commercial use... within a personal feed reader" — a public dashboard
doesn't qualify, and this project doesn't route around a source's stated
terms just because it's technically reachable (see app/scraper/compliance.py
and docs/ethics_compliance.md for the same principle applied to fares).

The Hindu's business feed is explicitly listed as a Sitemap entry in its
own robots.txt (https://www.thehindu.com/business/feeder/default.rss) —
about as clear a "yes, this is meant to be consumed" signal as a robots.txt
gives. Business Standard's /rss/ path carries no Disallow rule either.
Neither source publishes an "aviation"-specific feed (a few plausible-
looking slugs were tried and silently fell back to the generic Economy
feed instead of 404ing — not used here to avoid mislabeling generic news
as aviation-specific); both are broad business/economy feeds, so
app.news.fetch_news keyword-filters every item down to ones that actually
mention an airfare driver before it's shown.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NewsSourceInfo:
    id: str
    name: str
    domain: str
    path: str

    @property
    def url(self) -> str:
        return f"https://{self.domain}{self.path}"


NEWS_SOURCES: list[NewsSourceInfo] = [
    NewsSourceInfo(
        id="business_standard_economy",
        name="Business Standard — Economy",
        domain="www.business-standard.com",
        path="/rss/economy-102.rss",
    ),
    NewsSourceInfo(
        id="business_standard_companies",
        name="Business Standard — Companies",
        domain="www.business-standard.com",
        path="/rss/companies-101.rss",
    ),
    NewsSourceInfo(
        id="the_hindu_business",
        name="The Hindu — Business",
        domain="www.thehindu.com",
        path="/business/feeder/default.rss",
    ),
]
