# Per-carrier index & financial context methodology

## What this feature adds

Two related things, both scoped to real, sourced data only:

1. **Per-carrier index** (`app/index/carrier_index.py`, `/api/index/by-carrier`)
   — the same Laspeyres/Paasche/Fisher construction `app/index/construct.py`
   uses for the headline APIx number, computed again per carrier so a
   reader can see whether, say, SpiceJet's own fares moved differently
   from Akasa's, rather than only ever seeing the blended cheapest-of-
   either-carrier figure.
2. **Airline financial context** (`app/index/financial_context.py`,
   `/api/carriers/financial-context`) — each covered carrier's publicly
   disclosed quarterly revenue, net profit, and margin, shown as real,
   dated context next to their fare movement.

Both follow the same rule as everything else in this project: real data
only feeds anything presented as a number; nothing is estimated,
interpolated, or forecasted to fill a gap.

## Which carriers are covered, and why

| Carrier | Code | Financial context | Why |
|---|---|---|---|
| IndiGo (InterGlobe Aviation Ltd) | 6E | **Available** | NSE/BSE-listed (NSE: INDIGO); required by SEBI to publish quarterly results |
| SpiceJet Ltd | SG | **Available** | NSE/BSE-listed (NSE: SPICEJET); required by SEBI to publish quarterly results |
| Akasa Air | QP | Not available | Privately held (SNV Aviation Pvt Ltd); no public filings exist to source |
| Air India | AI | Not available | Wholly owned by Tata Sons since the Air India–Vistara merger; not listed, no public filings |
| Air India Express | IX | Not available | Wholly owned Air India (Tata Group) subsidiary; not separately listed |

This isn't a data-collection gap the way the fare-scraping compliance gate
sometimes is (see `docs/ethics_compliance.md`) — for the three "not
available" carriers there is no public filing to source *at all*,
regardless of scraping permission. `/api/carriers/financial-context`
reports this honestly per carrier (`available: false` plus a
plain-language `reason`), the same pattern `/api/compliance` already uses
for a scrape source blocked by robots.txt, rather than silently omitting
those carriers or leaving the dashboard implying no data exists yet.

## Where the quarterly figures come from

Every figure in `app/index/financial_context.FINANCIAL_REFERENCE` is a
real, consolidated, as-reported number from a specific, dated, named news
report of that carrier's actual quarterly results — cross-checked against
at least one independent second source where noted, and against the
carrier's own investor-relations press release where one was directly
reachable (IndiGo's Q1 FY26 figures, for example, are also confirmed via
`goindigo.in/press-releases/indigo-releases-q1-financial-results-of-fy-2026.html`).
Every entry carries its own `source_url`, `source_note`, and `filing_date`
— see the module for the full citation trail per quarter.

**This is a hand-verified, periodically-refreshed reference dataset, not
a live scrape** — exactly the same design as `app.config.
MOSPI_CPI_REFERENCE` and `WAGE_REFERENCE`, the other two pieces of real
external reference data this project already carries. A SEBI-listed
company publishes new results at most four times a year, so there is
nothing to gain from re-fetching on every dashboard load, and a great deal
to lose from trying to auto-parse a live investor-relations page or PDF
filing without a human verifying the extracted numbers against the real
filing first — this project's own rule against fabricated or
misread numbers applies to *how* a number gets into the codebase, not
just to whether one is a straight-up invention.

That said, **the compliance gate the problem statement asks for is not
skipped for this feature** — `check_investor_relations_compliance()`
fetches and evaluates the *live* robots.txt for each covered carrier's own
investor-relations page (`goindigo.in/information/investor-relations.html`,
`spicejet.com/investors.aspx`) through the exact same `ComplianceGate`
class the price scrapers use, fails closed under the same rules, and is
surfaced in the API response (`compliance.allowed`/`reason`) on every
request. It answers a real, live, useful question — "is this page
currently reachable under our own ethical-scraping rule?" — it's just
honestly not the mechanism that produced the numbers below, and this
document says so rather than implying otherwise.

## The real numbers (as of this writing, 2026-09)

**InterGlobe Aviation Ltd (IndiGo, 6E)** — consolidated, ₹ crore:

| Quarter | Period | Revenue (ops) | Net profit/(loss) | Margin | Filed |
|---|---|--:|--:|--:|---|
| Q1 FY26 | Apr–Jun 2025 | 20,496.3 | +2,176.3 | 10.62% | 2025-07-30 |
| Q2 FY26 | Jul–Sep 2025 | 18,555.3 | −2,581.7 | −13.91% | 2025-11-04 |
| Q3 FY26 | Oct–Dec 2025 | 24,541.0 | +549.8 | 2.24% | 2026-01-22 |
| Q4 FY26 | Jan–Mar 2026 | 22,438.4 | −2,536.9 | −11.31% | 2026-05-29 |
| Q1 FY27 | Apr–Jun 2026 | 24,584.1 | −238.0 | −0.97% | 2026-07-23 |

**SpiceJet Ltd (SG)** — consolidated, ₹ crore:

| Quarter | Period | Revenue (ops) | Net profit/(loss) | Margin | Filed |
|---|---|--:|--:|--:|---|
| Q4 FY25 | Jan–Mar 2025 | 1,446.4 | +325.0 | 22.47% | 2025-06-14 |
| Q1 FY26 | Apr–Jun 2025 | 1,120.2 | −238.0 | −21.25% | 2025-09-05 |
| Q2 FY26 | Jul–Sep 2025 | 792.4 | −621.3 | −78.44% | 2025-11-12 |
| Q3 FY26 | Oct–Dec 2025 | 1,408.0 | −262.0 | −18.61% | 2026-02-12 |

SpiceJet's Q4 FY26 and Q1 FY27 results were not found reported as of this
research pass (September 2026) and are deliberately left out of
`FINANCIAL_REFERENCE` rather than estimated. `net_margin_pct` is always
computed live from the two stored figures (`100 x net_profit_cr /
revenue_cr`), never stored as its own number, so it can never silently
drift from the two real inputs it's derived from.

IndiGo's swings to loss in Q2 FY26 and Q4 FY26 were both driven mainly by
foreign-exchange restatement on its large dollar-denominated lease/debt
book, not by fare revenue — the company separately disclosed a much
smaller underlying loss/profit excluding that forex effect in both
quarters (see each entry's `source_note`). The stored `net_profit_cr` is
always the real, consolidated, as-filed number regardless — this project
doesn't adjust a carrier's own disclosed figure, it just notes the
disclosed context for why it moved so a reader isn't left assuming ticket
pricing alone explains a multi-thousand-crore swing.

## Carrier weight ("market share on the tracked routes")

The full derivation and formula are documented in
`app/index/carrier_index.py`'s module docstring; summarized here because
it has a real, deliberate limitation worth stating plainly.

The DGCA city-pair traffic file this project already uses for route
weights (`data/reference/dgca_city_pair_traffic.csv`) has **no per-carrier
breakdown at all** — only city-pair passenger totals. DGCA does publish a
separate airline-wise market-share report, but that file is not part of
this project's data, and using a remembered or unverified figure for it
would be exactly the kind of fabricated number this project refuses
elsewhere.

So `carrier_weight` combines the real DGCA route weight this project
already has with something it does actually observe — which carrier(s)
this project's own scrapers found quoting a real price on each route:

```
carrier_weight(c) = Σ_r  w_r  ×  quotes(c, r) / quotes(*, r)
```

`w_r` is route `r`'s real DGCA-derived weight; `quotes(c, r)` is a count
of this project's own real, non-outlier, non-sold-out fare observations
for carrier `c` on route `r`. **This is a DGCA-route-weighted share of
this project's own observed quoting activity — not official DGCA or
industry passenger market share**, and is a materially smaller, more
specific claim. With only SpiceJet and Akasa currently live (see
`docs/ethics_compliance.md`), it mostly reflects which of the two had a
quotable fare on a given route on a given day, not fleet size or true
national traffic share. The dashboard and API must present it as exactly
what it is.

## The non-negotiable limitation: correlation, never a verdict

**A quarterly, network-wide margin cannot validate — or invalidate — a
single route's single-day fare, and no code in this feature claims it
can.**

A margin figure blends every route the carrier flies, every fare class,
three months of fuel/forex/labour costs, and whatever demand happened to
show up, into one number. A fare shown elsewhere on this dashboard is one
route, one moment, one advance-purchase window. They are not the same
kind of measurement, and averaging one down to look like a comment on the
other would be a category error dressed up as insight.

Concretely, using this project's own real data: SpiceJet's disclosed net
margin moved from **22.47% in Q4 FY25 to −21.25% the very next quarter
(Q1 FY26)** — a ~44-point swing in three months, driven by the airline's
own cited reasons (regional airspace restrictions, grounded aircraft
awaiting maintenance) that have nothing to do with any individual fare a
traveller saw on a specific route that quarter. Showing that swing next
to, say, "SpiceJet's average fare on DEL-BOM rose 12% this month" is
useful, real, dated context — and it is *not* evidence either way about
whether that 12% move was reasonable.

**What this feature will show**: a factual juxtaposition of two real,
dated numbers, worded like the problem statement's own example — *"Fares
on this carrier rose 18% this quarter; their last disclosed net margin
was 4.2%, up from 1.1% the prior quarter."*

**What this feature will never show, anywhere**: a computed "justified,"
"unjustified," "fair," or "unfair" label on any fare. There is no
`is_price_justified()`-shaped function anywhere in `financial_context.py`
or `carrier_index.py`, and `backend/tests/test_financial_context.py`
enforces this as a regression test two ways — scanning both modules for
any function/class name that even looks like a fairness verdict, and
walking the actual runtime output of every public function in both
modules for a key that does. If you're extending this feature and find
yourself about to write one, stop: return the two real numbers and let
the caller (or the reader) juxtapose them.

## What the dashboard shows

- The per-carrier index panel reuses the existing trend-chart component
  and its color/legend conventions — each carrier gets its own line next
  to the same "Balanced average (headline)" line already on the Overview
  tab, not a new visual language.
- The financial-context panel is visually and structurally separate from
  the fare-index lines — a distinct panel, not an overlay on the same
  chart — so there is no ambiguity about which numbers are real fare-index
  data and which are quarterly financial disclosures being placed next to
  them for context.
- A carrier marked "not available" shows its plain-language reason, the
  same honest-gap pattern already used for a compliance-blocked scrape
  source, rather than a blank space that could be misread as "the data
  just isn't in yet."
