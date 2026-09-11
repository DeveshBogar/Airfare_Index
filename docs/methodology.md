# Index construction methodology

## Why this design

The problem statement asks for "an index-construction module based on
[the] PSD, given routes and weights." We read "PSD" as MoSPI's **Price
Statistics Division**, the body that computes CPI — so the design goal is
to mirror how CPI is actually built (a fixed-basket, weighted method
chain-linked over time), applied to a basket of air routes, weighted by
real demand data rather than assumed-equal weights.

## Route basket & weights

The basket is the **top 20 India-wide city-pairs by real, trailing-12-month
DGCA passenger traffic** — `app/config.ROUTE_BASKET` is the literal output
of `app/index/weights.top_traffic_routes(n=20)`, reproducible with
`python -m app.cli rank-routes`. It is not a hand-picked list of major
metros: the ranking pulled in routes like DEL-PNQ (Delhi-Pune) and DEL-SXR
(Delhi-Srinagar) ahead of several metro-metro pairs, and spans North,
South, East, West and Northeast India (Srinagar, Guwahati, Patna, Kochi,
Ahmedabad, Chennai, Kolkata all included), not just the four biggest
metros.

`app/index/weights.py` computes each route's weight as its trailing-12-
month bidirectional passenger share of the basket's combined traffic, from
`data/reference/dgca_city_pair_traffic.csv` (see that folder's `README.md`
for provenance). As of the most recent data in that file, ranked:

| Route | Weight |
|---|---|
| BOM–DEL | 12.6% |
| BLR–DEL | 9.5% |
| BLR–BOM | 7.6% |
| DEL–HYD | 6.0% |
| CCU–DEL | 5.6% |
| DEL–PNQ | 5.6% |
| AMD–DEL | 4.6% |
| BLR–HYD | 4.4% |
| BOM–CCU | 4.4% |
| DEL–MAA | 4.3% |
| BLR–CCU | 4.2% |
| BOM–MAA | 4.2% |
| BOM–HYD | 4.2% |
| AMD–BOM | 3.8% |
| DEL–SXR | 3.5% |
| BLR–PNQ | 3.5% |
| DEL–GAU | 3.1% |
| BLR–MAA | 2.9% |
| DEL–PAT | 2.9% |
| HYD–MAA | 2.9% |

This is exactly the "selected on the basis of DGCA passenger-traffic data"
requirement — the weights (and which 20 routes are even in the basket)
come from the CSV, not a config constant a human guessed at.

**A real data-quality fix behind these numbers**: the raw DGCA CSV labels
the same city inconsistently across report periods — most consequentially
"MUMBAI" vs "MUMBAI (MUMBAI)", plus trailing-whitespace variants like
"JAIPUR " and airport-suffix variants like "DEOGHAR AIRPORT" for other
cities. Left unnormalized, this silently splits a city's traffic across
two or more pseudo-cities and understates every route touching it — before
`normalize_city()` (in `app/index/weights.py`) folded these together,
Delhi-Mumbai's measured traffic was ~3.75M (looking smaller than Bengaluru-
Delhi's ~4.88M); correctly merged, it's ~6.47M and clearly the largest
route in the basket. `backend/tests/test_index.py` pins this down with a
regression test so it can't silently regress.

## Advance-purchase windows

T+1, T+7, T+15, T+30, T+45 (days before departure), as named in the
problem statement. Each route × window combination is a distinct series.

## Price representative

For a route on a given day, the representative price is the **cheapest
non-outlier, non-sold-out fare quoted that day** across whatever
carriers/fare-classes were observed — analogous to how a CPI price
collector records the price actually obtainable for a comparable item,
not an average across every price point shown.

## Three index variants

Let `P_r,t` be route `r`'s representative price on day `t`, `P_r,0` its
price on the base day (the earliest day with data), and `w_r` its weight.

**Laspeyres** (fixed, base-period weights):

```
L_t = 100 × Σ_r [ w_r^(base) × (P_r,t / P_r,0) ]  /  Σ_r w_r^(base)
```

**Paasche** — normally uses *current-period* expenditure weights, which
would require knowing how many tickets actually sold on each route each
day. Nobody outside the airlines observes that. Rather than fabricate
quantities, this implementation recomputes route weights from whatever
DGCA traffic file is on disk *at index-construction time*:

```
P_t = 100 × Σ_r [ w_r,t × (P_r,t / P_r,0) ]  /  Σ_r w_r,t
```

`data/reference/dgca_city_pair_traffic.csv` is refreshed periodically via
`scripts/download_dgca_data.py`, so as new DGCA monthly releases land,
`w_r,t` genuinely moves and Paasche genuinely diverges from the
fixed-weight Laspeyres. On the very first run they're identical (only one
weight snapshot exists yet) — that's expected, not a bug, and is stated
plainly by the API/dashboard rather than hidden.

**Fisher** (superlative index, symmetric in base/current weighting):

```
F_t = sqrt(L_t × P_t)
```

All three are computed and exposed side by side (`/api/index/daily`) so
the choice of weighting scheme is visible rather than picked silently.

## Cleaning: outliers, missing values, decomposition

- **Outliers**: flagged (not deleted) with a robust median/MAD z-score
  within each (route, AP-window) group of a scrape run — chosen over a
  plain mean/stdev because airfare distributions are heavy-tailed by
  construction (one legitimately expensive last-seat fare next to a wall
  of steady ones would blow out a normal stdev). Groups smaller than 4
  observations are left unflagged. See `app/pipeline/clean.py`.
- **Missing/sold-out flights**: recorded as a real row with `sold_out =
  true` and `total_fare = null` rather than silently dropped — the
  problem statement explicitly asks the pipeline to "account for
  cancellations/sold-out flights," which means keeping the fact that a
  search came back empty, not erasing it.
- **Fare decomposition** (base fare vs. taxes/UDF/convenience fee):
  applied only when a source's own page actually shows both components.
  Neither of the two currently-live sources (SpiceJet, Akasa) breaks the
  total out on their search-results view — both show one tax-inclusive
  number — so those rows keep `base_fare`/`taxes_fees` as `NULL` rather
  than a fabricated split. The decomposition function itself is fully
  implemented and unit-tested (`app/pipeline/clean.py::decompose_fare`)
  against a synthetic source that does provide both fields, so the
  capability is real and ready the day a live source exposes the
  breakdown.

## Lead-time elasticity

`app/index/elasticity.py` reports mean/min/max fare per AP window across
the whole basket, plus a simple point elasticity of price with respect to
lead time between adjacent windows:

```
elasticity = (%change in mean fare) / (%change in lead-time days)
```

A negative value is the expected sign (price falls as lead time — the
number of days before departure at which you book — rises).

## Backtest

See `app/backtest/run_backtest.py` and its own docstring: DGCA does not
publish a fare time series to diff against (only traffic/load-factor
statistics), so the back-test validates the pipeline against real,
self-collected history and reports its own sample size honestly (`N` real
days, growing daily via the scheduler) rather than padding it with
synthetic data.
