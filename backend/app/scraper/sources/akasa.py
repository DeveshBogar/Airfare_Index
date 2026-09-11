"""Akasa Air adapter.

robots.txt (https://www.akasaair.com/robots.txt) carries no Disallow rules
at all for User-agent: * (only Sitemap entries) — confirmed against the
live robots.txt on 2026-09-04. Akasa's booking widget is a client-rendered
React form (react-datepicker for the calendar) with no query-string
shortcut to results, so this adapter drives the real form end to end. Every
selector below was verified against the live site during development
(see the exploration notes in docs/ethics_compliance.md), not guessed:
city fields are plain `#From`/`#To` inputs with a `<li>` autocomplete list,
the calendar exposes an unambiguous `aria-label` per day ("Choose
<Weekday>, <Month> <Day><suffix>, <Year>"), and the Search Flights button
carries a genuine `disabled` attribute we poll rather than racing.

Akasa's results page also surfaces nearby-airport alternatives (e.g. a
Delhi search can return Noida/Jewar, a Mumbai search can return Navi
Mumbai) — we only keep rows whose origin/destination exactly match what
was requested, so an alternate-airport fare never gets misattributed to
the route we're indexing.
"""
from __future__ import annotations

import datetime as dt
import re

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.config import AIRPORT_NAMES
from app.scraper.base import CaptchaDetected, RawQuote, SourceAdapter

_FLIGHT_ROW_RE = re.compile(
    r"(?P<flightno>QP\s?\d{3,4})\s*"
    r"(?P<depart>\d{2}:\d{2})\s*"
    r"(?P<orig>[A-Z]{3})\s*"
    r"(?:\([^)]*\)\s*)?"
    r"(?P<duration>\d+h\s*\d+m)\s*"
    r"(?:Non-stop|\d+\s*Stop[s]?)\s*"
    r"(?P<arrive>\d{2}:\d{2})\s*"
    r"(?P<dest>[A-Z]{3})\s*"
    r"(?:\([^)]*\)\s*)?"
    r"(?:Lowest fare\s*)?"
    r"Starting\s*"
    r"₹\s*(?P<price>[\d,]+)",
    re.MULTILINE,
)

_NO_FLIGHTS_MARKERS = ("no flights", "no results", "sorry, we couldn't find")


def _to_float(price_str: str) -> float:
    return float(price_str.replace(",", ""))


def _ordinal_suffix(day: int) -> str:
    if 11 <= day % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


async def _dismiss_cookie_banner(page: Page) -> None:
    try:
        btn = page.get_by_role("button", name="Close", exact=False)
        if await btn.count() > 0:
            await btn.first.click(timeout=2000)
    except Exception:
        pass


async def _select_city(page: Page, field_id: str, city_name: str) -> None:
    field = page.locator(f"#{field_id}")
    await field.click()
    await field.type(city_name, delay=60)
    option = page.locator("li", has_text=city_name).first
    await option.wait_for(state="visible", timeout=8000)
    await option.click()


async def _pick_date(page: Page, travel_date: dt.date) -> None:
    await page.click('input[name=DepartureDate]')
    month_year = travel_date.strftime("%B") + f" {travel_date.day}{_ordinal_suffix(travel_date.day)}, {travel_date.year}"

    # react-datepicker shows two months side by side; step forward until
    # the target date's cell exists (it may take >1 click if AP window
    # spans multiple months, e.g. T+45).
    for _ in range(4):
        cell = page.locator(f'[aria-label*="{month_year}"]')
        if await cell.count() > 0:
            await cell.first.click()
            break
        next_btn = page.locator(".react-datepicker__navigation--next")
        if await next_btn.count() == 0:
            break
        await next_btn.first.click()
        await page.wait_for_timeout(300)

    await page.mouse.click(400, 5)  # click outside the popup to close it and commit the value


class AkasaAdapter(SourceAdapter):
    source_id = "akasa"
    domain = "www.akasaair.com"
    carrier_code = "QP"
    compliance_paths = ["/flight-booking", "/flight-search"]

    # City name Akasa's autocomplete expects, per origin/destination IATA
    # code — kept in sync with the full airport list in app.config so an
    # expanded route basket doesn't silently break city selection here.
    CITY_NAMES = AIRPORT_NAMES

    async def collect(
        self,
        page: Page,
        origin: str,
        destination: str,
        travel_date: dt.date,
        ap_window_days: int,
        search_date: dt.date,
    ) -> list[RawQuote]:
        await page.goto(
            "https://www.akasaair.com/flight-booking",
            wait_until="domcontentloaded",
            timeout=45000,
        )
        await page.wait_for_timeout(1500)
        await _dismiss_cookie_banner(page)

        await _select_city(page, "From", self.CITY_NAMES.get(origin, origin))
        await _select_city(page, "To", self.CITY_NAMES.get(destination, destination))
        # Give the form's own async validation (triggered by the city
        # change) time to settle before we touch the date picker — opening
        # it too soon interrupts that in-flight update and leaves the
        # Search button stuck disabled even after a valid date is chosen.
        await page.wait_for_timeout(1200)
        await _pick_date(page, travel_date)

        search_btn = page.locator('button[name="Search Flights"]')
        enabled = False
        for _ in range(16):
            if await search_btn.get_attribute("disabled") is None:
                enabled = True
                break
            await page.wait_for_timeout(500)
        if not enabled:
            return []  # form never validated (e.g. same city, past date) — nothing to collect

        await search_btn.click(timeout=10000)

        try:
            await page.wait_for_url("**/flight-search**", timeout=15000)
        except PlaywrightTimeoutError:
            pass
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except PlaywrightTimeoutError:
            pass
        await page.wait_for_timeout(1500)

        if await self.detect_captcha(page):
            raise CaptchaDetected(f"akasa: challenge detected for {origin}-{destination}")

        body_text = await page.inner_text("body")

        if any(marker in body_text.lower() for marker in _NO_FLIGHTS_MARKERS):
            return [
                RawQuote(
                    origin=origin,
                    destination=destination,
                    carrier_code=self.carrier_code,
                    ap_window_days=ap_window_days,
                    search_date=search_date,
                    travel_date=travel_date,
                    fare_class="economy",
                    total_fare=None,
                    sold_out=True,
                )
            ]

        quotes: list[RawQuote] = []
        for m in _FLIGHT_ROW_RE.finditer(body_text):
            if m.group("orig") != origin or m.group("dest") != destination:
                continue  # nearby-airport alternative Akasa suggested — not the route we asked for
            quotes.append(
                RawQuote(
                    origin=origin,
                    destination=destination,
                    carrier_code=self.carrier_code,
                    ap_window_days=ap_window_days,
                    search_date=search_date,
                    travel_date=travel_date,
                    fare_class="economy",
                    total_fare=_to_float(m.group("price")),
                )
            )
        return quotes
