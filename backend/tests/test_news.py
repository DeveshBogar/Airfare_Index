from __future__ import annotations

import datetime as dt

import requests

from app.news.fetch_news import _fetch_all, _parse_feed, get_airfare_news
from app.news.keywords import categorize
from app.news.sources import NewsSourceInfo
from app.scraper.compliance import ComplianceGate

SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
  <title>Jet fuel prices push airlines to raise fares this festive season</title>
  <link>https://example.com/atf-hike</link>
  <description>ATF price hike expected to add pressure on ticket prices ahead of Diwali travel.</description>
  <pubDate>Fri, 11 Sep 2026 23:58:56 +0530</pubDate>
</item>
<item>
  <title>Steel tariffs rattle global trade talks</title>
  <link>https://example.com/steel</link>
  <description>Nothing to do with flights at all.</description>
  <pubDate>Fri, 11 Sep 2026 20:00:00 +0530</pubDate>
</item>
<item>
  <title>IndiGo adds new Delhi-Guwahati route</title>
  <link>https://example.com/indigo-route</link>
  <description>Capacity expansion announced by the carrier.</description>
  <pubDate>Thu, 10 Sep 2026 12:00:00 +0530</pubDate>
</item>
</channel></rss>
"""

NO_ROBOTS_RESTRICTION = "User-agent: *\nAllow: /\n"


def test_categorize_finds_fuel_and_fare_keywords():
    text = "atf price hike pushes flight fare higher"
    categories = categorize(text)
    assert "fuel" in categories
    assert "fare" in categories


def test_categorize_returns_empty_for_unrelated_text():
    assert categorize("steel tariffs rattle global trade talks") == []


def test_parse_feed_keeps_only_airfare_relevant_items():
    items = _parse_feed(SAMPLE_FEED, "Test Source")
    titles = {i.title for i in items}
    assert "Jet fuel prices push airlines to raise fares this festive season" in titles
    assert "IndiGo adds new Delhi-Guwahati route" in titles
    assert "Steel tariffs rattle global trade talks" not in titles


def test_parse_feed_sets_categories_and_strips_html():
    items = _parse_feed(SAMPLE_FEED, "Test Source")
    fuel_item = next(i for i in items if "Jet fuel" in i.title)
    assert "fuel" in fuel_item.categories
    assert "<" not in fuel_item.summary
    assert fuel_item.published_at is not None
    assert fuel_item.published_at.year == 2026


def test_fetch_all_dedupes_and_sorts_newest_first(monkeypatch):
    class FakeResp:
        def __init__(self, text: str):
            self.status_code = 200
            self.text = text

        def raise_for_status(self):
            return None

    def fake_get(url, *args, **kwargs):
        if url.endswith("/robots.txt"):
            return FakeResp(NO_ROBOTS_RESTRICTION)
        return FakeResp(SAMPLE_FEED)

    # compliance.py and fetch_news.py each do their own `import requests`,
    # but both names refer to the one shared requests module — patching its
    # `get` once here covers both the robots.txt fetch and the RSS fetch.
    monkeypatch.setattr("requests.get", fake_get)

    sources = [
        NewsSourceInfo(id="a", name="Source A", domain="a.example", path="/rss.xml"),
        NewsSourceInfo(id="b", name="Source B", domain="b.example", path="/rss.xml"),
    ]
    monkeypatch.setattr("app.news.fetch_news.NEWS_SOURCES", sources)

    result = _fetch_all(ComplianceGate())
    titles = [i.title for i in result.items]
    # same two items appear in both fake feeds — deduped down to 2, not 4
    assert len(titles) == 2
    # newest (23:58:56) sorts before the 12:00 item
    assert titles[0] == "Jet fuel prices push airlines to raise fares this festive season"
    assert len(result.sources_checked) == 2
    assert all(c.allowed for c in result.sources_checked)


def test_fetch_source_fails_closed_when_robots_txt_unreachable(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.exceptions.ConnectionError("no route to host")

    monkeypatch.setattr("app.scraper.compliance.requests.get", boom)
    monkeypatch.setattr(
        "app.news.fetch_news.NEWS_SOURCES",
        [NewsSourceInfo(id="a", name="Source A", domain="a.example", path="/rss.xml")],
    )

    result = _fetch_all(ComplianceGate())
    assert result.items == []
    assert result.sources_checked[0].allowed is False
    assert "could not be fetched" in result.sources_checked[0].reason


def test_get_airfare_news_caches_within_ttl(monkeypatch):
    calls = {"n": 0}

    def fake_fetch_all(gate):
        calls["n"] += 1
        return type("R", (), {"items": [], "as_of": dt.datetime.now(dt.timezone.utc), "sources_checked": []})()

    monkeypatch.setattr("app.news.fetch_news._fetch_all", fake_fetch_all)
    monkeypatch.setattr("app.news.fetch_news._cache", {})

    get_airfare_news()
    get_airfare_news()
    assert calls["n"] == 1  # second call served from cache, no re-fetch
