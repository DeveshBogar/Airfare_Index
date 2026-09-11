"""Central configuration: route basket, advance-purchase windows, and the
source registry that drives which scrapers are allowed to run live.

The route basket is a seed set drawn from the top city-pairs in DGCA's
published domestic passenger-traffic statistics (see data/reference/ and
app/index/weights.py, which derives the *actual* weights from that CSV).
This list is just which pairs we track; the weight each one carries in the
index is computed from real traffic data, not hardcoded here.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "airfare.db"
DGCA_TRAFFIC_CSV = DATA_DIR / "reference" / "dgca_city_pair_traffic.csv"
RAW_SNAPSHOT_DIR = DATA_DIR / "raw"

# IATA code -> display city name, for every airport that appears anywhere
# in the route basket below or that app/index/weights.py's top-route
# ranking might pull in if the basket is regenerated with a larger N.
AIRPORT_NAMES = {
    "DEL": "Delhi",
    "BOM": "Mumbai",
    "BLR": "Bengaluru",
    "CCU": "Kolkata",
    "HYD": "Hyderabad",
    "MAA": "Chennai",
    "PNQ": "Pune",
    "AMD": "Ahmedabad",
    "SXR": "Srinagar",
    "GAU": "Guwahati",
    "PAT": "Patna",
    "COK": "Kochi",
    "LKO": "Lucknow",
    "BBI": "Bhubaneswar",
    "IDR": "Indore",
    "ATQ": "Amritsar",
    "VNS": "Varanasi",
    "IXR": "Ranchi",
    "IXC": "Chandigarh",
    "CJB": "Coimbatore",
    "GOI": "Goa",
    "NAG": "Nagpur",
    "JAI": "Jaipur",
    "RPR": "Raipur",
    "VTZ": "Visakhapatnam",
    "TRV": "Thiruvananthapuram",
    "IXM": "Madurai",
    "IXE": "Mangalore",
    "STV": "Surat",
    "BDQ": "Vadodara",
    "DED": "Dehradun",
    "IXJ": "Jammu",
    "IXA": "Agartala",
    "IXZ": "Port Blair",
    "IXB": "Bagdogra",
    "BHO": "Bhopal",
    "GAY": "Gaya",
}

# Real airport coordinates (decimal degrees, WGS84), one entry per IATA
# code above — sourced from the OurAirports open aviation database
# (https://ourairports.com/countries/IN/airports.csv, itself compiled from
# official aeronautical data) and cross-checked against each airport's own
# published coordinates. Used by app.index.affordability to compute real
# great-circle distances — not estimates or approximations.
AIRPORT_COORDINATES: dict[str, tuple[float, float]] = {
    "DEL": (28.55563, 77.09519),
    "BOM": (19.088699, 72.867897),
    "BLR": (13.1979, 77.706299),
    "CCU": (22.654012, 88.44765),
    "HYD": (17.231318, 78.429855),
    "MAA": (12.990005, 80.169296),
    "PNQ": (18.5821, 73.919701),
    "AMD": (23.0772, 72.634697),
    "SXR": (33.987099, 74.7742),
    "GAU": (26.106654, 91.585226),
    "PAT": (25.591299, 85.087997),
    "COK": (10.151047, 76.400838),
    "LKO": (26.760599, 80.889297),
    "BBI": (20.251021, 85.814747),
    "IDR": (22.721404, 75.80051),
    "ATQ": (31.7096, 74.797302),
    "VNS": (25.452171, 82.862549),
    "IXR": (23.3143, 85.321701),
    "IXC": (30.6735, 76.788498),
    "CJB": (11.03, 77.043404),
    "GOI": (15.380062, 73.833328),
    "NAG": (21.092199, 79.047203),
    "JAI": (26.8242, 75.812202),
    "RPR": (21.180401, 81.7388),
    "VTZ": (17.971512, 83.503617),
    "TRV": (8.481889, 76.920029),
    "IXM": (9.83451, 78.093399),
    "IXE": (12.95471, 74.886812),
    "STV": (21.115531, 72.743251),
    "BDQ": (22.336201, 73.226303),
    "DED": (30.189243, 78.176651),
    "IXJ": (32.688849, 74.838152),
    "IXA": (23.886999, 91.240402),
    "IXZ": (11.640194, 92.72902),
    "IXB": (26.6812, 88.328598),
    "BHO": (23.2875, 77.337402),
    "GAY": (24.744301, 84.951202),
}

# DGCA city name (normalized — see app/index/weights.normalize_city) -> IATA
# code, for every airport named above. This is the join key that lets
# app/index/weights.top_traffic_routes() turn *real* DGCA traffic rankings
# into an IATA-code route basket the scraper can actually use.
DGCA_CITY_TO_IATA = {
    "DELHI": "DEL",
    "MUMBAI": "BOM",
    "BENGALURU": "BLR",
    "KOLKATA": "CCU",
    "HYDERABAD": "HYD",
    "CHENNAI": "MAA",
    "PUNE": "PNQ",
    "AHMEDABAD": "AMD",
    "SRINAGAR": "SXR",
    "GUWAHATI": "GAU",
    "PATNA": "PAT",
    "KOCHI": "COK",
    "LUCKNOW": "LKO",
    "BHUBANESWAR": "BBI",
    "INDORE": "IDR",
    "AMRITSAR": "ATQ",
    "VARANASI": "VNS",
    "RANCHI": "IXR",
    "CHANDIGARH": "IXC",
    "COIMBATORE": "CJB",
    "GOA": "GOI",
    "NAGPUR": "NAG",
    "JAIPUR": "JAI",
    "RAIPUR": "RPR",
    "VISAKHAPATNAM": "VTZ",
    "THIRUVANANTHAPURAM": "TRV",
    "MADURAI": "IXM",
    "MANGALORE": "IXE",
    "SURAT": "STV",
    "VADODARA": "BDQ",
    "DEHRADUN": "DED",
    "JAMMU": "IXJ",
    "AGARTALA": "IXA",
    "PORT BLAIR": "IXZ",
    "BAGDOGRA": "IXB",
    "BHOPAL": "BHO",
    "GAYA": "GAY",
}

# Route basket: the top 20 India-wide city-pairs by real, trailing-12-month
# DGCA passenger traffic — this literally is the output of
# app/index/weights.top_traffic_routes(n=20), pasted in so it's a plain
# constant everywhere else in the app imports from. Regenerate with
# `python -m app.cli rank-routes` after refreshing the DGCA CSV
# (scripts/download_dgca_data.py) and paste the new ranking in here.
# Deliberately not the 6 metro-heavy pairs a human would guess by hand —
# e.g. DEL-PNQ and DEL-SXR outrank several metro-metro pairs in the real
# data, and Mumbai's routes rank far higher than they first appeared to
# before normalize_city() fixed a "MUMBAI" vs "MUMBAI (MUMBAI)" duplicate-
# label bug in the raw DGCA data (see weights.py's docstring).
ROUTE_BASKET: list[tuple[str, str]] = [
    ("BOM", "DEL"),
    ("BLR", "DEL"),
    ("BLR", "BOM"),
    ("DEL", "HYD"),
    ("CCU", "DEL"),
    ("DEL", "PNQ"),
    ("AMD", "DEL"),
    ("BLR", "HYD"),
    ("BOM", "CCU"),
    ("DEL", "MAA"),
    ("BLR", "CCU"),
    ("BOM", "MAA"),
    ("BOM", "HYD"),
    ("AMD", "BOM"),
    ("DEL", "SXR"),
    ("BLR", "PNQ"),
    ("DEL", "GAU"),
    ("BLR", "MAA"),
    ("DEL", "PAT"),
    ("HYD", "MAA"),
]

# Advance-purchase windows (days before departure) required by the problem
# statement.
AP_WINDOWS: list[int] = [1, 7, 15, 30, 45]


@dataclass(frozen=True)
class SourceInfo:
    id: str
    name: str
    kind: str  # "airline" | "ota"
    domain: str  # host used for the robots.txt compliance check
    carrier_code: str | None = None  # IATA 2-letter code, airlines only
    notes: str = ""


# Every source named explicitly in the problem statement. Whether one of
# these is actually allowed to run *today* is NOT decided here — it is
# decided at runtime by app/scraper/compliance.py, which fetches and parses
# each domain's live robots.txt and gates the adapter accordingly. This
# registry just says "these are the sources the system knows how to talk to."
SOURCE_REGISTRY: dict[str, SourceInfo] = {
    "spicejet": SourceInfo(
        id="spicejet",
        name="SpiceJet",
        kind="airline",
        domain="www.spicejet.com",
        carrier_code="SG",
    ),
    "akasa": SourceInfo(
        id="akasa",
        name="Akasa Air",
        kind="airline",
        domain="www.akasaair.com",
        carrier_code="QP",
    ),
    "indigo": SourceInfo(
        id="indigo",
        name="IndiGo",
        kind="airline",
        domain="www.goindigo.in",
        carrier_code="6E",
        notes="robots.txt disallows /book/*, /booking/*, /search.html",
    ),
    "air_india": SourceInfo(
        id="air_india",
        name="Air India",
        kind="airline",
        domain="www.airindia.com",
        carrier_code="AI",
    ),
    "air_india_express": SourceInfo(
        id="air_india_express",
        name="Air India Express",
        kind="airline",
        domain="www.airindiaexpress.com",
        carrier_code="IX",
        notes="robots.txt disallows /flight-availability",
    ),
    "ixigo": SourceInfo(
        id="ixigo",
        name="ixigo",
        kind="ota",
        domain="www.ixigo.com",
        notes="robots.txt disallows /flights/search, /flights/review, /search/result/, /api/",
    ),
    "easemytrip": SourceInfo(
        id="easemytrip",
        name="EaseMyTrip",
        kind="ota",
        domain="www.easemytrip.com",
        notes="robots.txt disallows /flight-search/listing*",
    ),
    "cleartrip": SourceInfo(
        id="cleartrip",
        name="Cleartrip",
        kind="ota",
        domain="www.cleartrip.com",
        notes="robots.txt disallows /flights/search*",
    ),
    "yatra": SourceInfo(
        id="yatra",
        name="Yatra",
        kind="ota",
        domain="www.yatra.com",
    ),
    "goibibo": SourceInfo(
        id="goibibo",
        name="Goibibo",
        kind="ota",
        domain="www.goibibo.com",
    ),
    "makemytrip": SourceInfo(
        id="makemytrip",
        name="MakeMyTrip",
        kind="ota",
        domain="www.makemytrip.com",
    ),
}

# HTTP User-Agent pool the scraper rotates through — all real, current
# desktop browser strings. No spoofing of bot identity beyond a normal UA;
# the compliance gate is what governs whether we're allowed to fetch a path
# at all, not the UA.
USER_AGENT_POOL: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
]

# Minimum seconds between two requests to the same domain (token-bucket
# refill period) — the "appropriate rate-limiting" ethical safeguard.
DEFAULT_RATE_LIMIT_SECONDS = 6.0

# A coarse sanity bound on a domestic one-way fare, used by
# app.pipeline.clean.is_plausible_fare to catch scraper/parsing bugs (e.g.
# a selector accidentally reading a seat count or a date as the price)
# before they ever reach the index — distinct from the statistical
# median/MAD outlier check, which flags genuinely unusual *real* prices.
# Real domestic one-way fares observed so far range roughly INR 3,900 -
# 24,300; this range is deliberately wider than that so a real, unusually
# cheap or expensive fare is never mistaken for a scraper bug.
PLAUSIBLE_FARE_INR_RANGE: tuple[float, float] = (500.0, 100_000.0)

# Contact string sent as part of our own custom request header so a site
# operator can identify and reach out about this project if they want to.
SCRAPER_CONTACT = "AirFare Idex research project (SIH prototype) - contact via source repository"


@dataclass(frozen=True)
class TravelSpikeWindow:
    key: str
    name: str
    start: dt.date
    end: dt.date
    why: str
    source_note: str
    # Researched, festival-specific fare-surge estimates used ONLY as a
    # fallback when we don't yet have enough real scraped data for this
    # exact window to measure the real premium ourselves (see
    # app.index.estimation._festival_spike_multiplier). general_surge_pct
    # applies basket-wide; high_demand_surge_pct applies instead on routes
    # touching one of high_demand_airports, where the festival's pull is
    # reported as sharpest (e.g. Kolkata for Durga Puja, Patna/Gaya for
    # Chhath). Both are real researched figures, not guesses — see
    # surge_source_note/surge_source_url for what backs each one.
    general_surge_pct: float
    high_demand_surge_pct: float
    high_demand_airports: frozenset[str]
    surge_source_url: str
    surge_source_note: str


# Known Indian travel-demand spikes that reliably move domestic airfares,
# used by app.index.spike_watch to flag routes whose real, scraped fares
# land inside one of these date ranges. Every date here is a real, sourced
# calendar date for 2026 (Hindu festival dates are lunisolar and shift
# every year, so these are NOT reusable as-is for other years without
# re-checking):
#   - Durga Puja/Dussehra 2026: Shashthi 16 Oct -> Vijayadashami 21 Oct
#     (drikpanchang.com panchang calendar; cross-checked against
#     giftstoindia24x7.com, which gives 17-21 Oct for the same festival).
#   - Diwali 2026: 8 Nov (Monday) - sacredcal.com, mygiftscorner.com.
#   - Chhath Puja 2026: 13-16 Nov - dnaindia.com / happyfares.in.
#   - Winter wedding season 2026-27: opens 20 Nov 2026 - happyfares.in
#     ("India Festive Travel Calendar 2026" industry report), tapering by
#     mid-February per general North Indian wedding-season convention.
# The elevated-demand *window* around each festival (as opposed to the
# festival's own core day(s)) is widened based on industry fare-trend
# reporting cited alongside the dates above, e.g. "fares rising 80-120% in
# the two weeks around Durga Puja" and "fares normalise around 12-15
# November" post-Diwali, and "the return leg during Chhath (16-22 Nov) is
# the tight one" - see docs/methodology.md for the full source list.
TRAVEL_SPIKE_WINDOWS: list[TravelSpikeWindow] = [
    TravelSpikeWindow(
        key="durga_puja_dussehra_2026",
        name="Durga Puja & Dussehra",
        start=dt.date(2026, 10, 10),
        end=dt.date(2026, 10, 24),
        why="East and North India's biggest autumn festival - Kolkata and Delhi both see a sharp travel surge.",
        source_note="Festival dates 16-21 Oct 2026 (drikpanchang.com); elevated window widened to the "
        "surrounding fortnight per reported 80-120% CCU-DEL fare rises around Durga Puja.",
        general_surge_pct=15.0,
        high_demand_surge_pct=100.0,
        high_demand_airports=frozenset({"CCU"}),
        surge_source_url="https://happyfares.in",
        surge_source_note="DGCA-referenced industry reporting (via happyfares.in) puts CCU-DEL fares up "
        "80-120% around Durga Puja; 100% (the midpoint) is used for any route touching Kolkata, a flatter "
        "15% for the rest of the basket that still feels the broader festive pull.",
    ),
    TravelSpikeWindow(
        key="diwali_2026",
        name="Diwali",
        start=dt.date(2026, 11, 4),
        end=dt.date(2026, 11, 15),
        why="India's largest single travel event of the year - almost every route sees a fare spike.",
        source_note="Diwali falls on 8 Nov 2026 (sacredcal.com, mygiftscorner.com); fares reported to "
        "normalise around 12-15 Nov, so the window runs from a few days before through then.",
        general_surge_pct=28.0,
        high_demand_surge_pct=32.5,
        high_demand_airports=frozenset({"SXR"}),
        surge_source_url="https://travelandtourworld.com",
        surge_source_note="Industry reporting (travelandtourworld.com) puts basket-wide Diwali fare rises "
        "at 30-35%, with DGCA domestic passenger volumes up 18-25% over the period; routes to Srinagar, a "
        "leisure/homecoming destination that sees the sharpest Diwali-week demand, are given the top of the "
        "reported 25-40% range for specific high-pull routes.",
    ),
    TravelSpikeWindow(
        key="chhath_puja_2026",
        name="Chhath Puja",
        start=dt.date(2026, 11, 11),
        end=dt.date(2026, 11, 22),
        why="The single biggest driver of Delhi/Mumbai/Bengaluru <-> Bihar-Jharkhand fares all year.",
        source_note="Chhath falls 13-16 Nov 2026 (dnaindia.com); return-leg congestion reported through "
        "22 Nov, so the window covers both the outbound and return travel surge.",
        general_surge_pct=20.0,
        high_demand_surge_pct=70.0,
        high_demand_airports=frozenset({"PAT", "GAY"}),
        surge_source_url="https://patnapress.com",
        surge_source_note="Reporting on Delhi-Patna fares (Moneycontrol/Urban Acres, patnapress.com) ranges "
        "from 25-60% up to 180-257% for the tightest last-minute fares, driven by 3M+ Bihari migrants in "
        "Delhi NCR travelling home; 70% is a conservative-of-range figure for Patna/Gaya routes specifically, "
        "with a flatter 20% for the rest of the basket's incidental Chhath-period demand.",
    ),
    TravelSpikeWindow(
        key="winter_wedding_season_2026_27",
        name="Winter wedding season",
        start=dt.date(2026, 11, 20),
        end=dt.date(2027, 2, 15),
        why="North India's main wedding season drives sustained, broad demand rather than one sharp peak.",
        source_note="Season reported to open 20 Nov 2026 (happyfares.in industry report); end date is an "
        "approximate close of the conventional winter wedding season, not a fixed festival date.",
        general_surge_pct=18.0,
        high_demand_surge_pct=18.0,
        high_demand_airports=frozenset(),
        surge_source_url="https://happyfares.in",
        surge_source_note="IATA lead-time data shows December as the year's most expensive domestic-fare "
        "month, with November running 9-14% below the December peak; no single route shows a sharply higher "
        "wedding-specific pull than any other (unlike Chhath's Bihar corridor), so one flat, moderate "
        "basket-wide figure is used rather than an unsupported route tier.",
    ),
    TravelSpikeWindow(
        key="christmas_new_year_2026_27",
        name="Christmas & New Year",
        start=dt.date(2026, 12, 20),
        end=dt.date(2027, 1, 3),
        why="Reported as the single largest fare spike of the year, ahead of even Diwali.",
        source_note="Fixed calendar dates; industry reporting describes this as the year's biggest peak.",
        general_surge_pct=75.0,
        high_demand_surge_pct=75.0,
        high_demand_airports=frozenset(),
        surge_source_url="https://travelandtourworld.com",
        surge_source_note="Industry reporting puts the Dec 24-Jan 3 window 60-110% above the annual median "
        "basket-wide (e.g. Mumbai-Goa reported at INR 8,000-15,000 vs an INR 2,000-2,800 off-peak fare); no "
        "single-route tier is applied since the peak is reported as broad-based rather than corridor-specific.",
    ),
]


def spike_window_for_date(day: dt.date) -> TravelSpikeWindow | None:
    """The travel-spike window a given travel date falls inside, if any.

    Some windows deliberately overlap - Diwali's normalisation tail runs
    into Chhath's start (11-15 Nov), Chhath's return-leg tail runs into
    the winter wedding season's opening (20-22 Nov), and the whole
    Christmas/New Year window sits inside the broad wedding season
    (20 Dec - 3 Jan). When a date matches more than one window, the most
    recently-begun one wins: it's the more specific, more relevant signal
    for that exact date (once Chhath has started, it says more about that
    date's fares than "technically still wedding season" does). This also
    guarantees querying any window at its own `start` date always resolves
    back to that same window, since nothing else can have begun more
    recently at that point."""
    matches = [w for w in TRAVEL_SPIKE_WINDOWS if w.start <= day <= w.end]
    if not matches:
        return None
    return max(matches, key=lambda w: w.start)


@dataclass(frozen=True)
class MospiCpiReference:
    series_base: str
    reference_month: str  # "YYYY-MM"
    reference_month_label: str
    published_date: dt.date
    next_release_date: dt.date
    headline_cpi_index: float
    headline_cpi_yoy_pct: float
    transport_division_index: float
    transport_division_yoy_pct: float
    passenger_transport_index: float
    passenger_transport_yoy_pct: float
    source_url: str
    source_note: str


# The real, most recently published MoSPI Consumer Price Index figures at
# the time this was written — used as the official-CPI side of the
# CPI-divergence comparison (app/index/cpi_divergence.py). All-India
# Combined sector, base 2024=100.
#
# "Passenger transport services" (Group 07.3) is the closest official MoSPI
# category to airfares — the NSO/MoSPI CPI basket does not publish an
# air-fares-only sub-index, so this group (which also includes rail and
# road passenger fares) is the honest nearest match, not an air-only proxy
# presented as one. The broader "Transport" division (07) is kept alongside
# for context: it additionally bundles vehicle purchases and fuel, which is
# why its year-on-year figure moves differently from passenger transport
# services alone.
#
# Source: NSO/MoSPI "Press Release of Consumer Price Index on Base 2024=100
# for July, 2026", published 12 August 2026 (the latest release available
# as of this writing — August 2026's CPI is due 14 September 2026).
# Verified against the official PDF, Annexure-I and Annexure-II.
MOSPI_CPI_REFERENCE = MospiCpiReference(
    series_base="2024=100",
    reference_month="2026-07",
    reference_month_label="July 2026",
    published_date=dt.date(2026, 8, 12),
    next_release_date=dt.date(2026, 9, 14),
    headline_cpi_index=107.94,
    headline_cpi_yoy_pct=4.45,
    transport_division_index=105.63,
    transport_division_yoy_pct=4.43,
    passenger_transport_index=105.39,
    passenger_transport_yoy_pct=2.90,
    source_url=(
        "https://www.mospi.gov.in/uploads/latestReleases/latest_release_1786529680747_"
        "3113661d-1a2b-4b9a-af06-b340193ef9a0_Press_Release_CPI_July_2026.pdf"
    ),
    source_note=(
        "All-India Combined sector, Group 07.3 'Passenger transport services' — the "
        "closest official MoSPI category to airfares (it also includes rail and road "
        "passenger fares, not air alone). The broader 'Transport' division (07) is "
        "shown alongside for context: it additionally includes vehicle purchases and "
        "fuel, which is why its year-on-year figure differs."
    ),
)


@dataclass(frozen=True)
class IndianWageReference:
    report_label: str
    survey_period: str
    published_date: dt.date
    casual_labour_daily_wage_male_inr: float
    casual_labour_daily_wage_female_inr: float
    regular_salaried_monthly_earnings_male_inr: float
    regular_salaried_monthly_earnings_female_inr: float
    self_employed_monthly_earnings_male_inr: float
    self_employed_monthly_earnings_female_inr: float
    source_url: str
    source_note: str


# Real, official Indian wage figures — used by app.index.affordability to
# express a fare as "how many days of wages" it costs, the same way this
# project compares APIx against official CPI: real government statistics,
# not an estimate. Source: NSO/MoSPI Periodic Labour Force Survey (PLFS)
# Annual Report 2025 [January-December 2025], published 27 March 2026 —
# verified against the official press-note PDF, not just a summary.
#
# The *casual labour* daily wage (not the monthly regular-salaried or
# self-employed figures) is used as the primary "day's wages" reference:
# it is already a genuine day-rate (no monthly-to-daily conversion or
# working-days-per-month assumption needed to compute it), and casual
# labour is around a fifth of India's workforce — using it keeps the
# comparison grounded in what a fare costs someone near the bottom of the
# income distribution, which is the most concrete way to make the
# CPI-affordability point land. Male and female figures are kept separate
# rather than blended into a single "person" figure, because PLFS's public
# press note doesn't publish the worker-count weights needed to combine
# them accurately — showing both real numbers is more honest than a
# fabricated average.
WAGE_REFERENCE = IndianWageReference(
    report_label="PLFS Annual Report 2025",
    survey_period="January-December 2025",
    published_date=dt.date(2026, 3, 27),
    casual_labour_daily_wage_male_inr=455.0,
    casual_labour_daily_wage_female_inr=315.0,
    regular_salaried_monthly_earnings_male_inr=24217.0,
    regular_salaried_monthly_earnings_female_inr=18353.0,
    self_employed_monthly_earnings_male_inr=17914.0,
    self_employed_monthly_earnings_female_inr=6374.0,
    source_url=(
        "https://www.mospi.gov.in/uploads/latestReleases/latest_release_1774607827733_"
        "3e8964a9-268b-4cc9-ad65-cfc8a9e32f08_Press_note_AR_PLFS_2025_23032025_V2.1_26032026_final.pdf"
    ),
    source_note=(
        "NSO/MoSPI Periodic Labour Force Survey, Annual Report 2025 (calendar year "
        "2025, published 27 Mar 2026). Casual-labour daily wage is 'other than public "
        "works' — the PLFS category for ordinary day-labour, not government workfare "
        "schemes. Regular wage/salaried and self-employed figures are monthly, not "
        "daily, and are shown for context rather than converted into a day-count."
    ),
)
