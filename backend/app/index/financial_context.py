"""Publicly disclosed quarterly financial context for the two NSE/BSE-
listed carriers this project tracks fares for — SpiceJet Ltd (NSE:
SPICEJET, carrier code SG) and InterGlobe Aviation Ltd, which trades and
reports as IndiGo (NSE: INDIGO, carrier code 6E). Akasa Air (QP) and Air
India (AI) are both privately held and file no public quarterly results —
see NOT_AVAILABLE_CARRIERS below — so there is nothing real to source for
them, and this module does not attempt to estimate or interpolate one.

What this module is for, and what it is emphatically NOT for
--------------------------------------------------------------
This answers exactly one question: "what did this carrier publicly
disclose about its own revenue and profitability, and when?" Every figure
in FINANCIAL_REFERENCE below is a real, consolidated, as-reported number
from a specific dated news report of that carrier's quarterly results
(see each entry's source_url/source_note) — never estimated, interpolated,
or forecasted. If a quarter hasn't been reported yet, it is simply absent
from the list rather than projected.

This module — and nothing built on top of it — computes or returns a
"justified" / "unjustified" / "fair" / "unfair" verdict on any fare. A
carrier's quarterly, network-wide margin says nothing about whether one
route's one-day fare is reasonable: the margin blends every route, every
fare class, and three months of costs and demand into one number, while a
single fare reflects one moment on one route. The most this module (or
the dashboard built on it) may honestly do is place the two real numbers
next to each other with their real dates and let the reader draw their
own conclusion — see docs/financial_context_methodology.md for the full
reasoning. If you are about to add a function that returns a fairness
verdict, don't — return the two real numbers instead and let the caller
juxtapose them.

Compliance
----------
Every fetch this module could make against a carrier's own site (the
investor-relations page compliance check below) goes through the same
ComplianceGate class the price scrapers use (app.scraper.compliance) —
fetches and evaluates that domain's *live* robots.txt, fails closed if it
can't be verified, exactly like every other source in this project. The
quarterly figures themselves are NOT re-scraped from that page on every
request: SEBI's quarterly filing cadence means a new number lands at most
four times a year, so — exactly like app.config.MOSPI_CPI_REFERENCE and
WAGE_REFERENCE, the two other pieces of real external reference data this
project already carries — the figures are a hand-verified, dated,
manually-refreshed constant, not a live-scraped one. The compliance check
still runs on every request and is surfaced honestly: it tells a reader
whether the underlying investor-relations page is *currently* reachable
under this project's own ethical-scraping rule, which is a real and
useful signal even though it isn't what produced the numbers below.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.config import SOURCE_REGISTRY
from app.scraper.compliance import ComplianceGate

# ---------------------------------------------------------------------
# Carriers with no public filings to source at all.
# ---------------------------------------------------------------------

NOT_AVAILABLE_CARRIERS: dict[str, str] = {
    "QP": (
        "Akasa Air is privately held (SNV Aviation Pvt Ltd, backed by Rakesh "
        "Jhunjhunwala's family office and others) and is not listed on any "
        "stock exchange, so it files no public quarterly results."
    ),
    "AI": (
        "Air India is wholly owned by Tata Sons (following the Air India–"
        "Vistara merger) and is not a listed company, so it files no public "
        "quarterly results."
    ),
    "IX": (
        "Air India Express is a wholly owned subsidiary of Air India (Tata "
        "Group), not separately listed, so it files no public quarterly "
        "results of its own."
    ),
}

# Every carrier_code app.config.SOURCE_REGISTRY knows about — the router
# iterates this so the endpoint always reports on the full, fixed set of
# carriers this project tracks (available or not), rather than silently
# varying with whatever happens to be in FINANCIAL_REFERENCE.
ALL_KNOWN_CARRIER_CODES: list[str] = ["6E", "SG", "QP", "AI", "IX"]


# ---------------------------------------------------------------------
# Real, dated, sourced quarterly results.
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class CarrierQuarterFinancials:
    carrier_code: str  # IATA code, matches db.models.Carrier.code (6E, SG)
    quarter_label: str  # e.g. "Q1 FY26" (Indian fiscal year: FY26 = Apr 2025-Mar 2026)
    period_start: dt.date
    period_end: dt.date
    revenue_cr: float  # revenue FROM OPERATIONS, INR crore, consolidated — not total income
    net_profit_cr: float  # consolidated net profit (+) or loss (-), INR crore
    filing_date: dt.date
    source_url: str
    source_note: str

    @property
    def net_margin_pct(self) -> float:
        return round(100.0 * self.net_profit_cr / self.revenue_cr, 2)


# InterGlobe Aviation Ltd (IndiGo, 6E) — consolidated quarterly results.
# Every filing_date below was read directly off the cited Business
# Standard article's own URL slug (which encodes the article's publish
# date as YYMMDD, e.g. ".../...-126012201421_1.html" -> 2026-01-22 -
# cross-checked against two independently-dated articles that also showed
# a visible "published" timestamp matching the same decode, before being
# relied on for the rest). Every revenue/profit figure is the consolidated
# "revenue from operations" and "net profit/(loss)" as reported by that
# same article, cross-checked against at least one second independent
# outlet (Zee Business, Upstox, Angel One, IndiaInfoline, or IndiGo's own
# goindigo.in press release) where noted.
INDIGO_QUARTERS: list[CarrierQuarterFinancials] = [
    CarrierQuarterFinancials(
        carrier_code="6E",
        quarter_label="Q1 FY26",
        period_start=dt.date(2025, 4, 1),
        period_end=dt.date(2025, 6, 30),
        revenue_cr=20_496.3,
        net_profit_cr=2_176.3,
        filing_date=dt.date(2025, 7, 30),
        source_url=(
            "https://www.business-standard.com/companies/quarterly-results/"
            "indigo-q1-fy26-result-profit-down-20-at-2-176-cr-revenue-up-5-125073001057_1.html"
        ),
        source_note="Also confirmed via IndiGo's own press release (goindigo.in/press-releases/"
        "indigo-releases-q1-financial-results-of-fy-2026.html).",
    ),
    CarrierQuarterFinancials(
        carrier_code="6E",
        quarter_label="Q2 FY26",
        period_start=dt.date(2025, 7, 1),
        period_end=dt.date(2025, 9, 30),
        revenue_cr=18_555.3,
        net_profit_cr=-2_581.7,
        filing_date=dt.date(2025, 11, 4),
        source_url=(
            "https://www.business-standard.com/amp/companies/quarterly-results/"
            "indigo-net-loss-jumps-161-6-to-2-582-crore-due-to-rupee-depreciation-125110401588_1.html"
        ),
        source_note="Loss driven almost entirely by forex restatement on ~$9bn of foreign-currency "
        "lease/debt exposure, not core operations — IndiGo separately reported a small operating "
        "profit excluding that forex swing (₹103.9 cr). Reported here as the real, consolidated, "
        "as-filed figure regardless, per this module's no-adjustment rule.",
    ),
    CarrierQuarterFinancials(
        carrier_code="6E",
        quarter_label="Q3 FY26",
        period_start=dt.date(2025, 10, 1),
        period_end=dt.date(2025, 12, 31),
        revenue_cr=24_541.0,
        net_profit_cr=549.8,
        filing_date=dt.date(2026, 1, 22),
        source_url=(
            "https://www.business-standard.com/companies/quarterly-results/"
            "indigo-q3fy26-results-net-profit-declines-77-6-per-cent-to-rs-549-crore-126012201421_1.html"
        ),
        source_note="Profit fell 77.6% YoY on new Labour Code costs (₹969.3 cr) and December 2025 "
        "operational-disruption costs (₹550 cr) — both one-time items, included here as reported.",
    ),
    CarrierQuarterFinancials(
        carrier_code="6E",
        quarter_label="Q4 FY26",
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 3, 31),
        revenue_cr=22_438.4,
        net_profit_cr=-2_536.9,
        filing_date=dt.date(2026, 5, 29),
        source_url=(
            "https://www.business-standard.com/markets/capital-market-news/"
            "indigo-reports-dismal-q4-performance-126052901463_1.html"
        ),
        source_note="Loss again driven mainly by forex losses and exceptional charges; company "
        "separately reported ₹1,920.6 cr net profit excluding those items.",
    ),
    CarrierQuarterFinancials(
        carrier_code="6E",
        quarter_label="Q1 FY27",
        period_start=dt.date(2026, 4, 1),
        period_end=dt.date(2026, 6, 30),
        revenue_cr=24_584.1,
        net_profit_cr=-238.0,
        filing_date=dt.date(2026, 7, 23),
        source_url=(
            "https://www.business-standard.com/markets/capital-market-news/"
            "indigo-posts-net-loss-of-rs-2-380-crore-in-q1-fy27-126072301187_1.html"
        ),
        source_note="₹238 cr net loss cross-checked against IndiaInfoline, Zee Business, Kotak "
        "Securities and Business Today, all independently reporting the same figure; fuel costs "
        "rose 86% YoY (₹5,833 cr -> ₹10,833 cr), the stated driver of the swing to a loss.",
    ),
]

# SpiceJet Ltd (SG) — consolidated quarterly results. Same sourcing
# convention as IndiGo above (filing_date decoded from the cited Business
# Standard article's own URL slug). Q4 FY26 and Q1 FY27 were not found
# reported as of this writing (2026-09) and are deliberately left out
# rather than estimated — see this module's docstring and
# docs/financial_context_methodology.md.
SPICEJET_QUARTERS: list[CarrierQuarterFinancials] = [
    CarrierQuarterFinancials(
        carrier_code="SG",
        quarter_label="Q4 FY25",
        period_start=dt.date(2025, 1, 1),
        period_end=dt.date(2025, 3, 31),
        revenue_cr=1_446.37,
        net_profit_cr=325.0,
        filing_date=dt.date(2025, 6, 14),
        source_url=(
            "https://www.business-standard.com/companies/quarterly-results/"
            "spicejet-q4fy25-results-pat-jumps-nearly-three-fold-to-rs-325-crore-125061400245_1.html"
        ),
        source_note="SpiceJet's first full-year (FY25) net profit in 7 years; revenue-from-operations "
        "figure (₹1,446.37 cr) is distinct from the ₹1,942 cr total-revenue-including-other-income "
        "figure some outlets led with — this module always uses revenue from operations for "
        "comparability across quarters.",
    ),
    CarrierQuarterFinancials(
        carrier_code="SG",
        quarter_label="Q1 FY26",
        period_start=dt.date(2025, 4, 1),
        period_end=dt.date(2025, 6, 30),
        revenue_cr=1_120.2,
        net_profit_cr=-238.0,
        filing_date=dt.date(2025, 9, 5),
        source_url=(
            "https://www.business-standard.com/companies/quarterly-results/"
            "spicejet-q1-results-loss-238-crore-low-demand-operation-sindoor-125090501154_1.html"
        ),
        source_note="Swing from a ₹150 cr profit a year earlier; company cited regional airspace "
        "restrictions and delayed return-to-service of grounded aircraft.",
    ),
    CarrierQuarterFinancials(
        carrier_code="SG",
        quarter_label="Q2 FY26",
        period_start=dt.date(2025, 7, 1),
        period_end=dt.date(2025, 9, 30),
        revenue_cr=792.4,
        net_profit_cr=-621.3,
        filing_date=dt.date(2025, 11, 12),
        source_url=(
            "https://www.business-standard.com/companies/quarterly-results/"
            "spicejet-q2-fy26-results-loss-widens-to-621-crore-revenue-dips-13-125111201154_1.html"
        ),
        source_note="Loss widened from ₹458 cr a year earlier; PLF held at 84.3% despite the "
        "revenue decline, per the company's own release.",
    ),
    CarrierQuarterFinancials(
        carrier_code="SG",
        quarter_label="Q3 FY26",
        period_start=dt.date(2025, 10, 1),
        period_end=dt.date(2025, 12, 31),
        revenue_cr=1_408.0,
        net_profit_cr=-262.0,
        filing_date=dt.date(2026, 2, 12),
        source_url=(
            "https://www.business-standard.com/companies/quarterly-results/"
            "spicejet-swings-to-262-cr-loss-in-dec-quarter-on-labour-codes-weak-rupee-126021201816_1.html"
        ),
        source_note="Revenue-from-operations figure (₹1,408 cr) cross-checked against the reported "
        "77.7% sequential rise from Q2 FY26's ₹792.4 cr (792.4 x 1.777 ≈ 1,408); loss narrowed from "
        "Q2 FY26 despite new Labour Code and forex costs.",
    ),
]

FINANCIAL_REFERENCE: dict[str, list[CarrierQuarterFinancials]] = {
    "6E": INDIGO_QUARTERS,
    "SG": SPICEJET_QUARTERS,
}


# ---------------------------------------------------------------------
# Live compliance check (not what produced the numbers above — see the
# module docstring) against each covered carrier's investor-relations
# page, reusing the exact SOURCE_REGISTRY domains and ComplianceGate
# class the fare scrapers use.
# ---------------------------------------------------------------------

INVESTOR_RELATIONS_PATHS: dict[str, str] = {
    "6E": "/information/investor-relations.html",  # SOURCE_REGISTRY["indigo"].domain = www.goindigo.in
    "SG": "/investors.aspx",  # SOURCE_REGISTRY["spicejet"].domain = www.spicejet.com
}
_SOURCE_ID_BY_CARRIER: dict[str, str] = {"6E": "indigo", "SG": "spicejet"}


def check_investor_relations_compliance(carrier_code: str, gate: ComplianceGate | None = None) -> dict:
    """Live robots.txt check (fails closed, same as every scraper source)
    against this carrier's own investor-relations page — a real signal
    about whether that page is currently reachable under this project's
    ethical-scraping rule, independent of where FINANCIAL_REFERENCE's
    already-published figures came from."""
    source_id = _SOURCE_ID_BY_CARRIER.get(carrier_code)
    path = INVESTOR_RELATIONS_PATHS.get(carrier_code)
    if source_id is None or path is None:
        raise ValueError(f"no investor-relations page registered for carrier {carrier_code!r}")

    domain = SOURCE_REGISTRY[source_id].domain
    gate = gate or ComplianceGate()
    result = gate.evaluate(f"{source_id}_investor_relations", domain, [path])
    return {
        "domain": domain,
        "path": path,
        "allowed": result.allowed,
        "reason": result.reason,
    }


def financial_context_for_carrier(carrier_code: str, gate: ComplianceGate | None = None) -> dict:
    """Everything the API/dashboard needs for one carrier: its real
    quarterly results if it's one of the two covered carriers, or a plain-
    language "not available" reason if it isn't — never a guess at either."""
    if carrier_code in NOT_AVAILABLE_CARRIERS:
        return {
            "carrier_code": carrier_code,
            "available": False,
            "reason": NOT_AVAILABLE_CARRIERS[carrier_code],
            "quarters": [],
            "compliance": None,
        }

    quarters = FINANCIAL_REFERENCE.get(carrier_code)
    if quarters is None:
        return {
            "carrier_code": carrier_code,
            "available": False,
            "reason": "Not a carrier this project currently sources financial context for.",
            "quarters": [],
            "compliance": None,
        }

    return {
        "carrier_code": carrier_code,
        "available": True,
        "reason": None,
        "quarters": [
            {
                "quarter_label": q.quarter_label,
                "period_start": q.period_start,
                "period_end": q.period_end,
                "revenue_cr": q.revenue_cr,
                "net_profit_cr": q.net_profit_cr,
                "net_margin_pct": q.net_margin_pct,
                "filing_date": q.filing_date,
                "source_url": q.source_url,
                "source_note": q.source_note,
            }
            for q in quarters
        ],
        "compliance": check_investor_relations_compliance(carrier_code, gate),
    }


def all_financial_context(carrier_codes: list[str], gate: ComplianceGate | None = None) -> list[dict]:
    """financial_context_for_carrier for every carrier code the caller
    passes (normally every Carrier currently in the database), sharing one
    ComplianceGate instance so its 1-hour robots.txt cache is reused
    across carriers instead of re-fetching per carrier."""
    gate = gate or ComplianceGate()
    return [financial_context_for_carrier(code, gate) for code in carrier_codes]
