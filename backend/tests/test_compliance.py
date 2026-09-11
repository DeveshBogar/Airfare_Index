"""Unit tests for the robots.txt compliance gate — parsed against saved
robots.txt fixture text captured from the live sites on 2026-09-04
(app/scraper/compliance.py's own docstring explains why: several of these
files use wildcard syntax stdlib robotparser can't handle)."""
from __future__ import annotations

import requests

from app.scraper.compliance import ComplianceGate, parse_robots_txt

IXIGO_ROBOTS = """
User-agent: *
Disallow: /search/result/
Disallow: /flights/search
Disallow: /flights/review
Disallow: /*.pdf$
Disallow: /api/
"""

SPICEJET_ROBOTS = """
User-agent: *
Disallow:
Disallow: /cgi-bin/
Disallow: https://www.spicejet.com/api/v1
Disallow: https://www.spicejet.com/externalBooking
"""

AKASA_ROBOTS = """
User-Agent: *
Sitemap: https://www.akasaair.com/sitemap.xml
"""

CLEARTRIP_ROBOTS = """
User-agent: *
Allow: /
Disallow: /flights/search*
Disallow: /users/
"""


def test_wildcard_disallow_blocks_matching_path():
    policy = parse_robots_txt(IXIGO_ROBOTS)
    allowed, reason = policy.can_fetch("*", "/flights/search")
    assert allowed is False
    assert "Disallow" in reason


def test_wildcard_disallow_does_not_block_unrelated_path():
    policy = parse_robots_txt(IXIGO_ROBOTS)
    allowed, _ = policy.can_fetch("*", "/about-us")
    assert allowed is True


def test_trailing_dollar_anchors_end_of_string():
    policy = parse_robots_txt(IXIGO_ROBOTS)
    assert policy.can_fetch("*", "/report.pdf")[0] is False
    # a real robots.txt "$"-anchored rule shouldn't block a path that only
    # happens to contain the extension as a substring, not a suffix
    assert policy.can_fetch("*", "/report.pdf.html")[0] is True


def test_empty_disallow_value_means_allow_all():
    policy = parse_robots_txt(SPICEJET_ROBOTS)
    assert policy.can_fetch("*", "/search")[0] is True


def test_absolute_url_style_disallow_still_blocks_its_path():
    # SpiceJet's robots.txt writes "Disallow: https://www.spicejet.com/api/v1"
    # instead of a bare path — our parser normalizes this to a path match.
    policy = parse_robots_txt(SPICEJET_ROBOTS)
    allowed, _ = policy.can_fetch("*", "/api/v1/foo")
    assert allowed is False


def test_no_disallow_rules_means_everything_allowed():
    policy = parse_robots_txt(AKASA_ROBOTS)
    assert policy.can_fetch("*", "/flight-booking")[0] is True
    assert policy.can_fetch("*", "/anything/at/all")[0] is True


def test_allow_overrides_broader_disallow_when_more_specific():
    policy = parse_robots_txt(CLEARTRIP_ROBOTS)
    # "/" (Allow) is a shorter match than "/flights/search*" (Disallow),
    # so the more specific Disallow should win for a search path
    allowed, _ = policy.can_fetch("*", "/flights/search/results")
    assert allowed is False
    # but any other path just falls back to the blanket Allow: /
    assert policy.can_fetch("*", "/help")[0] is True


def test_gate_fails_closed_when_robots_txt_unreachable(monkeypatch):
    gate = ComplianceGate()

    def boom(*args, **kwargs):
        raise requests.exceptions.ConnectionError("no route to host")

    monkeypatch.setattr("app.scraper.compliance.requests.get", boom)
    result = gate.evaluate("fake", "does-not-resolve.example", ["/search"])
    assert result.allowed is False
    assert "could not be fetched" in result.reason


def test_gate_evaluate_allows_when_all_paths_permitted(monkeypatch):
    gate = ComplianceGate()

    class FakeResp:
        status_code = 200
        text = AKASA_ROBOTS

    monkeypatch.setattr("app.scraper.compliance.requests.get", lambda *a, **k: FakeResp())
    result = gate.evaluate("akasa", "www.akasaair.com", ["/flight-booking"])
    assert result.allowed is True
