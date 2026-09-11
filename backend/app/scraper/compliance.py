"""Runtime robots.txt compliance gate.

This is the ethical-scraping safeguard the problem statement asks for: no
source is scraped without first fetching and evaluating its *live*
robots.txt (not a hardcoded assumption baked in at design time — sites
change their policy, and this checks fresh every cache window). Rules
support the same wildcard syntax (`*`, trailing `$`) that real-world
robots.txt files use — several of the OTAs we audited (ixigo, easemytrip)
rely on wildcards, so Python's stdlib `urllib.robotparser` (which has no
wildcard support) isn't sufficient here.

If robots.txt cannot be fetched at all (network error, 5xx), the gate
fails *closed*: the source is treated as not-allowed rather than assuming
permission. A 404 (no robots.txt published) is treated as "no restrictions
stated" per the de-facto standard.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import requests

from app.config import SCRAPER_CONTACT

CACHE_TTL_SECONDS = 3600
OUR_USER_AGENT = f"AirFareIdexBot/1.0 (+{SCRAPER_CONTACT})"


def _normalize_pattern(pattern: str) -> str:
    """Some real robots.txt files (SpiceJet's included) write a full
    absolute URL as the Disallow value instead of a bare path — strip the
    scheme+host so it's matched as the path it clearly means, rather than
    silently never matching anything (a bare request path never starts
    with 'https://')."""
    if pattern.startswith("http://") or pattern.startswith("https://"):
        split = urlsplit(pattern)
        return split.path + (f"?{split.query}" if split.query else "")
    return pattern


def _compile_rule(pattern: str) -> re.Pattern[str]:
    """Compile a robots.txt path pattern into a regex, honoring the
    de-facto extensions most real robots.txt files use: '*' = wildcard,
    trailing '$' = end-of-string anchor."""
    pattern = _normalize_pattern(pattern)
    anchored_end = pattern.endswith("$")
    core = pattern[:-1] if anchored_end else pattern
    segments = core.split("*")
    regex = ".*".join(re.escape(seg) for seg in segments)
    if anchored_end:
        regex += "$"
    return re.compile("^" + regex)


@dataclass
class Rule:
    kind: str  # "allow" | "disallow"
    pattern: str
    regex: re.Pattern[str]


@dataclass
class RobotsPolicy:
    groups: dict[str, list[Rule]] = field(default_factory=dict)
    sitemaps: list[str] = field(default_factory=list)

    def _rules_for(self, user_agent: str) -> list[Rule]:
        ua = user_agent.lower()
        for key, rules in self.groups.items():
            if key != "*" and key and key in ua:
                return rules
        return self.groups.get("*", [])

    def can_fetch(self, user_agent: str, path: str) -> tuple[bool, str]:
        best: Rule | None = None
        for rule in self._rules_for(user_agent):
            if rule.regex.match(path):
                if best is None or len(rule.pattern) > len(best.pattern):
                    best = rule
                elif len(rule.pattern) == len(best.pattern) and rule.kind == "allow":
                    best = rule
        if best is None:
            return True, "no matching rule in robots.txt (default allow)"
        if best.kind == "allow":
            return True, f"matched 'Allow: {best.pattern}'"
        return False, f"matched 'Disallow: {best.pattern}'"


def parse_robots_txt(text: str) -> RobotsPolicy:
    groups: dict[str, list[Rule]] = {}
    sitemaps: list[str] = []
    current_agents: list[str] = []
    group_open = False  # true while we're still inside a run of User-agent lines

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        field_name = field_name.strip().lower()
        value = value.strip()

        if field_name == "user-agent":
            ua = value.lower()
            if not group_open:
                current_agents = [ua]
                group_open = True
            else:
                current_agents.append(ua)
            groups.setdefault(ua, [])
        elif field_name in ("disallow", "allow"):
            group_open = False
            if field_name == "disallow" and not value:
                continue  # "Disallow:" with empty value means allow-all
            rule = Rule(kind=field_name, pattern=value, regex=_compile_rule(value))
            for agent in current_agents or ["*"]:
                groups.setdefault(agent, []).append(rule)
        elif field_name == "sitemap":
            sitemaps.append(value)

    return RobotsPolicy(groups=groups, sitemaps=sitemaps)


@dataclass
class PathDecision:
    path: str
    allowed: bool
    reason: str


@dataclass
class ComplianceResult:
    source_id: str
    domain: str
    allowed: bool
    decisions: list[PathDecision]
    reason: str
    checked_at: float = field(default_factory=time.time)


class ComplianceGate:
    """Fetches and caches robots.txt per domain, evaluates whether a source
    is allowed to be scraped right now."""

    def __init__(self, cache_ttl_seconds: float = CACHE_TTL_SECONDS) -> None:
        self._cache: dict[str, tuple[float, RobotsPolicy | None]] = {}
        self._ttl = cache_ttl_seconds

    def _get_policy(self, domain: str) -> RobotsPolicy | None:
        now = time.time()
        cached = self._cache.get(domain)
        if cached and (now - cached[0]) < self._ttl:
            return cached[1]

        url = f"https://{domain}/robots.txt"
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": OUR_USER_AGENT})
        except requests.RequestException:
            self._cache[domain] = (now, None)
            return None

        if resp.status_code == 404:
            policy = RobotsPolicy()
        elif resp.status_code >= 400:
            policy = None
        else:
            policy = parse_robots_txt(resp.text)

        self._cache[domain] = (now, policy)
        return policy

    def evaluate(
        self,
        source_id: str,
        domain: str,
        paths: list[str],
        user_agent: str = OUR_USER_AGENT,
    ) -> ComplianceResult:
        policy = self._get_policy(domain)
        if policy is None:
            return ComplianceResult(
                source_id=source_id,
                domain=domain,
                allowed=False,
                decisions=[PathDecision(p, False, "robots.txt unreachable") for p in paths],
                reason="robots.txt could not be fetched — failing closed, not scraping",
            )

        decisions = []
        for path in paths:
            ok, why = policy.can_fetch(user_agent, path)
            decisions.append(PathDecision(path=path, allowed=ok, reason=why))

        allowed = all(d.allowed for d in decisions)
        if allowed:
            reason = "all representative paths permitted by the live robots.txt"
        else:
            blocked = ", ".join(f"{d.path} ({d.reason})" for d in decisions if not d.allowed)
            reason = f"blocked by robots.txt: {blocked}"

        return ComplianceResult(
            source_id=source_id,
            domain=domain,
            allowed=allowed,
            decisions=decisions,
            reason=reason,
        )
