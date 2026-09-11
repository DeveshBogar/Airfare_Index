"""Download the real DGCA city-pair domestic passenger-traffic dataset used
to derive route weights for the Airfare Price Index.

Primary source: DGCA's own "City pair wise monthly domestic passenger
traffic statistics" (https://www.dgca.gov.in/digigov-portal/?page=monthlyStatistics/259/4751/html),
mirrored and kept up to date as clean CSV by the open-source project
Vonter/india-aviation-traffic (https://github.com/Vonter/india-aviation-traffic),
which scrapes the same DGCA releases and the Wayback Machine for historical
coverage. Licensed ODbL-1.0 (Open Database License) — attribution required
and preserved here and in docs/methodology.md.

Run:
    python scripts/download_dgca_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.config import DGCA_TRAFFIC_CSV  # noqa: E402

SOURCE_URL = (
    "https://raw.githubusercontent.com/Vonter/india-aviation-traffic/"
    "main/aggregated/domestic/city.csv"
)


def main() -> None:
    DGCA_TRAFFIC_CSV.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading real DGCA city-pair traffic data from {SOURCE_URL}")
    resp = requests.get(SOURCE_URL, timeout=30)
    resp.raise_for_status()
    DGCA_TRAFFIC_CSV.write_bytes(resp.content)
    n_lines = resp.text.count("\n")
    print(f"Wrote {n_lines} rows to {DGCA_TRAFFIC_CSV}")


if __name__ == "__main__":
    main()
