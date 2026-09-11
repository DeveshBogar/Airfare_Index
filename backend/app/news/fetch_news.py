"""Fetches real headlines from the sources in app.news.sources, keeps only
the ones that actually mention an airfare driver (app.news.keywords), and
serves them to app.routers.news.

This deliberately never claims a headline caused a specific index move —
that would be a causal claim this module has no basis for. It surfaces
real, dated, sourced news about the same things that move airfares (fuel
cost, regulation, airline capacity, travel demand, disruption) so a reader
can connect it to the trend themselves, the same "here's the real data,
draw your own conclusion" stance the rest of the app takes (see
app.index.cpi_divergence, app.index.spike_watch).

Every fetch is gated by a live robots.txt check (app.scraper.compliance,
the same class the price scrapers use) and results are cached in-process
for CACHE_TTL_SECONDS so a dashboard that polls every 60 seconds doesn't
hammer three news sites every minute — see NEWS_SOURCES's docstring for
why these particular sources and not others.
"""
from __future__ import annotations

import datetime as dt
import html
import re
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import requests

from app.config import SCRAPER_CONTACT
from app.news.keywords import categorize
from app.news.sources import NEWS_SOURCES, NewsSourceInfo
from app.scraper.compliance import ComplianceGate

CACHE_TTL_SECONDS = 900  # 15 min — news doesn't need per-minute freshness
FETCH_TIMEOUT_SECONDS = 8
MAX_ITEMS = 12
OUR_USER_AGENT = f"AirFareIdexBot/1.0 (+{SCRAPER_CONTACT})"

_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published_at: dt.datetime | None
    categories: list[str]
    summary: str


@dataclass
class SourceCheck:
    name: str
    allowed: bool
    reason: str


@dataclass
class NewsResult:
    items: list[NewsItem]
    as_of: dt.datetime
    sources_checked: list[SourceCheck] = field(default_factory=list)


def _clean_text(raw: str | None) -> str:
    if not raw:
        return ""
    return html.unescape(_TAG_RE.sub("", raw)).strip()


def _parse_pubdate(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _parse_feed(xml_text: str, source_name: str) -> list[NewsItem]:
    root = ElementTree.fromstring(xml_text)
    items: list[NewsItem] = []
    for el in root.iter("item"):
        title = _clean_text(el.findtext("title"))
        link = (el.findtext("link") or "").strip()
        if not title or not link:
            continue
        summary = _clean_text(el.findtext("description"))
        text = f"{title} {summary}".lower()
        categories = categorize(text)
        if not categories:
            continue  # not about anything that plausibly moves airfares
        items.append(
            NewsItem(
                title=title,
                link=link,
                source=source_name,
                published_at=_parse_pubdate(el.findtext("pubDate")),
                categories=categories,
                summary=summary[:220],
            )
        )
    return items


def _fetch_source(source: NewsSourceInfo, gate: ComplianceGate) -> tuple[list[NewsItem], SourceCheck]:
    result = gate.evaluate(source.id, source.domain, [source.path])
    if not result.allowed:
        return [], SourceCheck(name=source.name, allowed=False, reason=result.reason)

    try:
        resp = requests.get(source.url, timeout=FETCH_TIMEOUT_SECONDS, headers={"User-Agent": OUR_USER_AGENT})
        resp.raise_for_status()
        items = _parse_feed(resp.text, source.name)
    except (requests.RequestException, ElementTree.ParseError) as e:
        return [], SourceCheck(name=source.name, allowed=True, reason=f"fetch failed: {e}")

    return items, SourceCheck(name=source.name, allowed=True, reason=f"{len(items)} relevant item(s) found")


def _fetch_all(gate: ComplianceGate) -> NewsResult:
    all_items: list[NewsItem] = []
    checks: list[SourceCheck] = []
    for source in NEWS_SOURCES:
        items, check = _fetch_source(source, gate)
        all_items.extend(items)
        checks.append(check)

    seen: set[str] = set()
    deduped: list[NewsItem] = []
    for item in all_items:
        key = _normalize_title(item.title)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    deduped.sort(key=lambda i: i.published_at or dt.datetime.min.replace(tzinfo=dt.timezone.utc), reverse=True)

    return NewsResult(items=deduped[:MAX_ITEMS], as_of=dt.datetime.now(dt.timezone.utc), sources_checked=checks)


_cache: dict[str, tuple[float, NewsResult]] = {}


def get_airfare_news(gate: ComplianceGate | None = None, force_refresh: bool = False) -> NewsResult:
    now = time.time()
    cached = _cache.get("result")
    if not force_refresh and cached and (now - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]

    result = _fetch_all(gate or ComplianceGate())
    _cache["result"] = (now, result)
    return result
