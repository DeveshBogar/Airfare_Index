"""Adapters for sources whose robots.txt currently disallows the search
path they'd need (IndiGo, Air India, Air India Express — booking/search
flow disallowed or the domain blocks non-browser HTTP entirely; ixigo,
EaseMyTrip, Cleartrip, Yatra, Goibibo, MakeMyTrip — OTA search/listing
paths disallowed).

The parsing logic here is real and unit-tested against local HTML/text
fixtures (see backend/tests/fixtures/) — never against the live disallowed
pages, since fetching those pages even to "test" the parser would be the
same violation the compliance gate exists to prevent. `collect()` is only
ever invoked by the runner for a source the ComplianceGate has evaluated
as allowed; for every source wired up here that's currently false, so in
production these adapters are registered but dormant until a robots.txt
change, or a data-sharing/API agreement, flips them on.
"""
from __future__ import annotations

import datetime as dt
import re

from playwright.async_api import Page

from app.scraper.base import CaptchaDetected, RawQuote, SourceAdapter

_AIRLINE_FLIGHT_RE = re.compile(
    r"(?P<depart>\d{2}:\d{2})[\s\S]{0,80}?"
    r"(?P<arrive>\d{2}:\d{2}(?:\+1)?)[\s\S]{0,80}?"
    r"(?P<flightno>[A-Z0-9]{2}\s?\d{2,4})[\s\S]{0,120}?"
    r"₹\s*(?P<price>[\d,]+)",
    re.MULTILINE,
)

_OTA_FLIGHT_RE = re.compile(
    r"(?P<carrier>6E|AI|IX|QP|SG)\s?-?\s?(?P<flightno>\d{2,4})[\s\S]{0,150}?"
    r"₹\s*(?P<price>[\d,]+)",
    re.MULTILINE,
)


def _to_float(price_str: str) -> float:
    return float(price_str.replace(",", ""))


def parse_airline_fare_text(text: str, carrier_code: str) -> list[dict]:
    """Pure text -> fare-row parser, exercised directly by unit tests
    against saved fixture text so the extraction logic is verified without
    ever requesting the live (disallowed) page."""
    return [
        {"carrier_code": carrier_code, "flight_no": m.group("flightno"), "total_fare": _to_float(m.group("price"))}
        for m in _AIRLINE_FLIGHT_RE.finditer(text)
    ]


def parse_ota_fare_text(text: str) -> list[dict]:
    return [
        {
            "carrier_code": m.group("carrier"),
            "flight_no": m.group("flightno"),
            "total_fare": _to_float(m.group("price")),
        }
        for m in _OTA_FLIGHT_RE.finditer(text)
    ]


class GenericGatedAirlineAdapter(SourceAdapter):
    """Base for a single-carrier airline site whose booking/search flow is
    currently disallowed by robots.txt (or unreachable by plain HTTP)."""

    search_url_template: str = ""

    async def collect(
        self,
        page: Page,
        origin: str,
        destination: str,
        travel_date: dt.date,
        ap_window_days: int,
        search_date: dt.date,
    ) -> list[RawQuote]:
        url = self.search_url_template.format(
            origin=origin, destination=destination, date=travel_date.isoformat()
        )
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        if await self.detect_captcha(page):
            raise CaptchaDetected(f"{self.source_id}: challenge detected for {origin}-{destination}")
        body_text = await page.inner_text("body")
        rows = parse_airline_fare_text(body_text, self.carrier_code or "")
        return [
            RawQuote(
                origin=origin,
                destination=destination,
                carrier_code=row["carrier_code"],
                ap_window_days=ap_window_days,
                search_date=search_date,
                travel_date=travel_date,
                fare_class="economy",
                total_fare=row["total_fare"],
            )
            for row in rows
        ]


class IndiGoAdapter(GenericGatedAirlineAdapter):
    source_id = "indigo"
    domain = "www.goindigo.in"
    carrier_code = "6E"
    compliance_paths = ["/booking/flight-select", "/search.html"]
    search_url_template = (
        "https://www.goindigo.in/booking/flight-select"
        "?origin={origin}&destination={destination}&departureDate={date}&paxType=A-1"
    )


class AirIndiaAdapter(GenericGatedAirlineAdapter):
    source_id = "air_india"
    domain = "www.airindia.com"
    carrier_code = "AI"
    compliance_paths = ["/book/flight-select"]
    search_url_template = (
        "https://www.airindia.com/book/flight-select"
        "?origin={origin}&destination={destination}&departureDate={date}&adults=1"
    )


class AirIndiaExpressAdapter(GenericGatedAirlineAdapter):
    source_id = "air_india_express"
    domain = "www.airindiaexpress.com"
    carrier_code = "IX"
    compliance_paths = ["/flight-availability"]
    search_url_template = (
        "https://www.airindiaexpress.com/flight-availability"
        "?origin={origin}&destination={destination}&date={date}&adults=1"
    )


class GenericOTAAdapter(SourceAdapter):
    """Base for a multi-carrier OTA whose flight-search/listing path is
    disallowed by robots.txt."""

    search_url_template: str = ""
    carrier_code = None

    async def collect(
        self,
        page: Page,
        origin: str,
        destination: str,
        travel_date: dt.date,
        ap_window_days: int,
        search_date: dt.date,
    ) -> list[RawQuote]:
        url = self.search_url_template.format(
            origin=origin, destination=destination,
            origin_lower=origin.lower(), destination_lower=destination.lower(),
            date=travel_date.isoformat(),
        )
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        if await self.detect_captcha(page):
            raise CaptchaDetected(f"{self.source_id}: challenge detected for {origin}-{destination}")
        body_text = await page.inner_text("body")
        rows = parse_ota_fare_text(body_text)
        return [
            RawQuote(
                origin=origin,
                destination=destination,
                carrier_code=row["carrier_code"],
                ap_window_days=ap_window_days,
                search_date=search_date,
                travel_date=travel_date,
                fare_class="economy",
                total_fare=row["total_fare"],
            )
            for row in rows
        ]


class IxigoAdapter(GenericOTAAdapter):
    source_id = "ixigo"
    domain = "www.ixigo.com"
    compliance_paths = ["/flights/search"]
    search_url_template = "https://www.ixigo.com/flights/search/result/{origin}/{destination}/{date}/1/0/0/E"


class EaseMyTripAdapter(GenericOTAAdapter):
    source_id = "easemytrip"
    domain = "www.easemytrip.com"
    compliance_paths = ["/flight-search/listing"]
    search_url_template = (
        "https://www.easemytrip.com/flight-search/listing"
        "?From={origin}&To={destination}&Date={date}&AdultCount=1"
    )


class CleartripAdapter(GenericOTAAdapter):
    source_id = "cleartrip"
    domain = "www.cleartrip.com"
    compliance_paths = ["/flights/search"]
    search_url_template = (
        "https://www.cleartrip.com/flights/search?adults=1&from={origin}&to={destination}&depart_date={date}"
    )


class YatraAdapter(GenericOTAAdapter):
    source_id = "yatra"
    domain = "www.yatra.com"
    compliance_paths = ["/air/domestic-flight-listing"]
    search_url_template = (
        "https://www.yatra.com/air/domestic-flight-listing"
        "?orig={origin}&dest={destination}&dt={date}&adt=1"
    )


class GoibiboAdapter(GenericOTAAdapter):
    source_id = "goibibo"
    domain = "www.goibibo.com"
    compliance_paths = ["/flights/air-del-bom-1"]  # representative path shape; goibibo.com/flights/air-<origin>-<dest>-1
    search_url_template = "https://www.goibibo.com/flights/air-{origin_lower}-{destination_lower}-1/?dt={date}&ADT=1"


class MakeMyTripAdapter(GenericOTAAdapter):
    source_id = "makemytrip"
    domain = "www.makemytrip.com"
    compliance_paths = ["/flight/search"]
    search_url_template = (
        "https://www.makemytrip.com/flight/search?itinerary={origin}-{destination}-{date}&tripType=O&paxType=A-1"
    )
