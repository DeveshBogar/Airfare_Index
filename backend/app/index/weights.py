"""Route weights derived from real DGCA city-pair passenger-traffic data —
this is the "selected on the basis of DGCA passenger-traffic data" input
the problem statement asks for, computed fresh from the CSV rather than
hardcoded.

DGCA's file reports each city-pair once per month with two directional
passenger counts (PaxToCity2 = City1->City2, PaxFromCity2 = City2->City1).
A route's traffic weight is its trailing-12-month bidirectional passenger
total as a share of the basket's combined total.

City names in the raw CSV are genuinely messy — trailing whitespace
("JAIPUR " vs "JAIPUR"), airport-suffix variants ("DEOGHAR AIRPORT"), and
outright duplicate labels for the same city across report periods (most
consequentially "MUMBAI" vs "MUMBAI (MUMBAI)", which — unnormalized —
silently splits Mumbai's true traffic across two pseudo-cities and
understates every Mumbai route's weight). normalize_city() below fixes
this before anything gets aggregated; it is applied everywhere a DGCA city
name is read, not just at the edges.
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

from app.config import AIRPORT_NAMES, DGCA_CITY_TO_IATA, DGCA_TRAFFIC_CSV, ROUTE_BASKET

_CITY_ALIASES = {
    "MUMBAI (MUMBAI)": "MUMBAI",
    "GOA (DABOLIM, SOUTH GOA)": "GOA",
    "COCHIN": "KOCHI",
    "MANGALORE (MANGALURU)": "MANGALORE",
    "NASIK": "NASHIK",
    "PUDUCHERRY": "PONDICHERRY",
    "PONDICHERRY (PUDUCHERRY)": "PONDICHERRY",
    "ALLAHABAD (PRAYAGRAJ)": "PRAYAGRAJ",
    "HISSAR": "HISAR",
    "CUDDAPAH (KADAPA)": "CUDDAPAH",
    "KADAPA": "CUDDAPAH",
    "DEHRA DUN": "DEHRADUN",
    "BIDAR AIRPORT, KARNATAKA": "BIDAR",
    "KALABURAGI, KARNATAKA": "KALABURAGI",
}

_SUFFIXES_TO_STRIP = (" INTERNATIONAL AIRPORT", " AIRPORT")


def normalize_city(raw: str) -> str:
    """Canonicalizes a DGCA City1/City2 value: trims whitespace, drops
    "...AIRPORT" suffixes, and resolves known duplicate/renamed-city
    labels to one name. Idempotent."""
    name = (raw or "").strip().upper()
    for suffix in _SUFFIXES_TO_STRIP:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return _CITY_ALIASES.get(name, name)


def load_traffic_df() -> pd.DataFrame:
    df = pd.read_csv(DGCA_TRAFFIC_CSV)
    df["period"] = df["Year"].astype(str) + "-" + df["Month"].astype(str).str.zfill(2)
    df["city1_norm"] = df["City1"].map(normalize_city)
    df["city2_norm"] = df["City2"].map(normalize_city)
    return df


def _recent(df: pd.DataFrame, trailing_months: int) -> pd.DataFrame:
    periods_sorted = sorted(df["period"].unique())
    recent_periods = set(periods_sorted[-trailing_months:])
    return df[df["period"].isin(recent_periods)]


def compute_route_weights(
    route_basket: list[tuple[str, str]] | None = None,
    trailing_months: int = 12,
) -> dict[tuple[str, str], dict]:
    """Returns {(origin, destination): {"passengers": float, "weight": float,
    "periods": [...]}} for the given basket, normalized so weights sum to 1
    across the basket."""
    route_basket = route_basket or ROUTE_BASKET
    recent = _recent(load_traffic_df(), trailing_months)

    results: dict[tuple[str, str], dict] = {}
    for origin, destination in route_basket:
        o_name = normalize_city(AIRPORT_NAMES.get(origin, origin))
        d_name = normalize_city(AIRPORT_NAMES.get(destination, destination))
        mask = ((recent["city1_norm"] == o_name) & (recent["city2_norm"] == d_name)) | (
            (recent["city1_norm"] == d_name) & (recent["city2_norm"] == o_name)
        )
        subset = recent[mask]
        passengers = float(subset["PaxToCity2"].sum() + subset["PaxFromCity2"].sum())
        results[(origin, destination)] = {
            "passengers": passengers,
            "periods": sorted(subset["period"].unique().tolist()),
        }

    grand_total = sum(r["passengers"] for r in results.values()) or 1.0
    for r in results.values():
        r["weight"] = r["passengers"] / grand_total

    return results


def top_traffic_routes(
    n: int = 20,
    trailing_months: int = 12,
    exclude: set[tuple[str, str]] | None = None,
) -> list[tuple[tuple[str, str], float]]:
    """Ranks *every* city-pair in the DGCA file by real trailing-month
    traffic and returns the top `n`, restricted to city pairs where both
    ends are in DGCA_CITY_TO_IATA (i.e. we have an IATA code to scrape
    with) — this is what config.ROUTE_BASKET was generated from. Returns
    [((origin_iata, destination_iata), total_passengers), ...] sorted
    descending by traffic.
    """
    recent = _recent(load_traffic_df(), trailing_months)
    exclude = exclude or set()

    pair_totals: dict[tuple[str, str], float] = defaultdict(float)
    for c1, c2, pax_to, pax_from in zip(
        recent["city1_norm"], recent["city2_norm"], recent["PaxToCity2"], recent["PaxFromCity2"]
    ):
        if c1 == c2 or c1 not in DGCA_CITY_TO_IATA or c2 not in DGCA_CITY_TO_IATA:
            continue
        iata_pair = tuple(sorted([DGCA_CITY_TO_IATA[c1], DGCA_CITY_TO_IATA[c2]]))
        if iata_pair in exclude:
            continue
        pair_totals[iata_pair] += float(pax_to or 0) + float(pax_from or 0)

    ranked = sorted(pair_totals.items(), key=lambda kv: -kv[1])
    return ranked[:n]
