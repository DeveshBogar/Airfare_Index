"""Common interface every source adapter implements, plus the CAPTCHA /
anti-bot detection helper shared across adapters.

Design principle: an adapter's job is to behave like a single real visitor
loading a permitted page and reading what renders — not to hit internal
JSON APIs directly, not to solve challenges, and not to push further into
a booking funnel than reading the fare list. That keeps every adapter on
the right side of both the robots.txt compliance gate and the "never
bypass CAPTCHA/bot-detection" rule.
"""
from __future__ import annotations

import datetime as dt
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

from playwright.async_api import Page

from app.config import USER_AGENT_POOL


@dataclass
class RawQuote:
    """One fare observation exactly as read off a source, before cleaning."""

    origin: str
    destination: str
    carrier_code: str
    ap_window_days: int
    search_date: dt.date
    travel_date: dt.date
    fare_class: str
    total_fare: float | None
    base_fare: float | None = None
    taxes_fees: float | None = None
    sold_out: bool = False
    raw_snapshot_path: str = ""
    source_id: str = ""


class CaptchaDetected(Exception):
    """Raised by an adapter when it detects a CAPTCHA / bot-detection
    challenge. Adapters must never attempt to solve or bypass this — the
    runner catches it, backs off, and skips the request."""


class SourceAdapter(ABC):
    source_id: str
    domain: str
    # Representative paths the compliance gate checks against robots.txt
    # before this adapter is ever allowed to run. Keep this in sync with
    # the paths collect() actually navigates to.
    compliance_paths: list[str]
    carrier_code: str | None = None

    def random_user_agent(self) -> str:
        return random.choice(USER_AGENT_POOL)

    @staticmethod
    async def detect_captcha(page: Page) -> bool:
        """Heuristic CAPTCHA / bot-challenge detection. Never used to solve
        anything — only to know when to back off."""
        markers = [
            "text=/verify you are human/i",
            "text=/are you a robot/i",
            "iframe[src*='recaptcha']",
            "iframe[src*='hcaptcha']",
            "div#challenge-running",  # Cloudflare
            "div.px-captcha-container",  # PerimeterX
        ]
        for marker in markers:
            try:
                locator = page.locator(marker)
                if await locator.count() > 0:
                    return True
            except Exception:
                continue
        return False

    @abstractmethod
    async def collect(
        self,
        page: Page,
        origin: str,
        destination: str,
        travel_date: dt.date,
        ap_window_days: int,
        search_date: dt.date,
    ) -> list[RawQuote]:
        """Navigate to the permitted search page for one route/date/window
        and return every fare observed. Must raise CaptchaDetected (not
        swallow it) if a challenge is hit."""
        raise NotImplementedError
