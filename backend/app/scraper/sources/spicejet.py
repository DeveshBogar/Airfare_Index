"""SpiceJet adapter.

robots.txt (https://www.spicejet.com/robots.txt) disallows only /cgi-bin/,
/api/v1, /public/ and /externalBooking for User-agent: *. The public search
results page (/search?...) is not disallowed, so this is one of the two
sources the compliance gate currently lets run live (confirmed against the
live robots.txt on 2026-09-04).

The results page takes plain query parameters, so we navigate directly to
it rather than driving the interactive form — one request per route/date
instead of several. We then read the *rendered* page text (exactly what a
human visitor sees) rather than calling the site's internal JSON APIs
directly, even though a couple of those (v2/v3) aren't disallowed either —
reading only what the page itself displays keeps us unambiguously on the
"normal visitor" side of the line.
"""
from __future__ import annotations

import datetime as dt
import re

from playwright.async_api import Page

from app.scraper.base import CaptchaDetected, RawQuote, SourceAdapter

_FLIGHT_BLOCK_RE = re.compile(
    r"(?P<depart>\d{2}:\d{2})\s*"
    r"(?P<orig>[A-Z]{3})\s*"
    r"Flight Details\s*"
    r"(?P<duration>\d+h\s*\d+m)\s*"
    r"(?P<arrive>\d{2}:\d{2}(?:\+1)?)\s*"
    r"(?P<dest>[A-Z]{3})\s*"
    r"(?P<flightno>SG\s?\d{2,4})\s*"
    r"(?P<stops>Direct|Hopping flight[^\n₹]*|Connecting[^\n₹]*)\s*"
    r"₹\s*(?P<saver>[\d,]+)[^₹]*"
    r"₹\s*(?P<flex>[\d,]+)[^₹]*"
    r"₹\s*(?P<max>[\d,]+)",
    re.MULTILINE,
)

_NO_FLIGHTS_MARKERS = ("No flights found", "Sorry, no results", "No flight available")


def _to_float(price_str: str) -> float:
    return float(price_str.replace(",", ""))


class SpiceJetAdapter(SourceAdapter):
    source_id = "spicejet"
    domain = "www.spicejet.com"
    carrier_code = "SG"
    compliance_paths = ["/search"]

    async def collect(
        self,
        page: Page,
        origin: str,
        destination: str,
        travel_date: dt.date,
        ap_window_days: int,
        search_date: dt.date,
    ) -> list[RawQuote]:
        url = (
            "https://www.spicejet.com/search"
            f"?from={origin}&to={destination}&tripType=1"
            f"&departure={travel_date.isoformat()}"
            "&adult=1&child=0&srCitizen=0&infant=0&currency=INR&redirectTo=/"
        )
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)

        if await self.detect_captcha(page):
            raise CaptchaDetected(f"spicejet: challenge detected for {origin}-{destination}")

        try:
            await page.wait_for_selector("text=/\\u20b9/", timeout=20000)
        except Exception:
            pass  # fall through to text scrape; may be a genuine no-flights day

        body_text = await page.inner_text("body")

        if any(marker.lower() in body_text.lower() for marker in _NO_FLIGHTS_MARKERS):
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
        for m in _FLIGHT_BLOCK_RE.finditer(body_text):
            for fare_class, key in (("spicesaver", "saver"), ("spiceflex", "flex"), ("spicemax", "max")):
                quotes.append(
                    RawQuote(
                        origin=origin,
                        destination=destination,
                        carrier_code=self.carrier_code,
                        ap_window_days=ap_window_days,
                        search_date=search_date,
                        travel_date=travel_date,
                        fare_class=fare_class,
                        total_fare=_to_float(m.group(key)),
                    )
                )
        return quotes
