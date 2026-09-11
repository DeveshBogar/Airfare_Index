"""Keyword rules that decide whether a news item is actually relevant to
airfares. Both source feeds (app.news.sources) are general business/economy
feeds, not aviation-specific ones, so most of what they publish (steel
tariffs, IPOs, forex reserves, ...) has nothing to do with airfares — this
is the filter that keeps only what does.

Deliberately a plain keyword match, not a model-scored "relevance", so
every inclusion is explainable and reproducible: a reader can see exactly
which phrase in the headline or summary earned it a spot. Categories are
the same five levers that actually move airfares in real reporting and
in this project's own methodology (see app.config.TRAVEL_SPIKE_WINDOWS
for the demand side, app.index.estimation for the cost-driver side) —
this module doesn't invent a new taxonomy, it just names news to the one
already in use.
"""
from __future__ import annotations

CATEGORY_LABELS: dict[str, str] = {
    "fuel": "Fuel cost",
    "regulatory": "Regulation & policy",
    "airline": "Airline & capacity",
    "demand": "Travel demand",
    "disruption": "Disruption",
}

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "fuel": [
        "atf price",
        "atf hike",
        "jet fuel",
        "aviation turbine fuel",
        "crude oil price",
        "fuel surcharge",
        "fuel price hike",
        "brent crude",
    ],
    "regulatory": [
        "dgca",
        "ministry of civil aviation",
        "civil aviation ministry",
        "airfare cap",
        "fare cap",
        "aviation regulator",
        "udan scheme",
        "airport tariff",
        "aera ",
    ],
    "airline": [
        "indigo",
        "air india",
        "spicejet",
        "akasa air",
        "vistara",
        "air india express",
        "airline capacity",
        "flight route",
        "new route",
        "route expansion",
        "airline earnings",
        "airline profit",
        "airline loss",
    ],
    "demand": [
        "festival travel",
        "diwali travel",
        "durga puja travel",
        "chhath travel",
        "holiday travel rush",
        "wedding season travel",
        "travel demand surge",
        "flight bookings surge",
        "air travel demand",
    ],
    "disruption": [
        "flight cancelled",
        "flights cancelled",
        "flight delay",
        "flights grounded",
        "airport closed",
        "airspace closure",
        "fog delay",
        "cyclone",
        "pilot strike",
        "airline strike",
        "monsoon disruption",
    ],
    "fare": [
        "airfare",
        "air fare",
        "flight fare",
        "flight ticket price",
        "ticket price",
        "fare hike",
        "fare war",
        "flight price",
    ],
}


def categorize(text: str) -> list[str]:
    """Every category whose keyword appears in `text` (already lowercased
    by the caller). Order follows CATEGORY_KEYWORDS's declaration order."""
    matched = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            matched.append(category)
    return matched
