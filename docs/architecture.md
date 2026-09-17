# Architecture

```
                    ┌──────────────────────────┐
 DGCA traffic CSV → │ app/index/weights.py     │ → route weights (real data)
 (data/reference/)  └──────────────────────────┘
                                  │
┌────────────┐   robots.txt   ┌──▼───────────────┐   raw JSONL    ┌──────────────┐
│ 11 registered│──gate check──▶│ scraper/runner.py │──snapshots────▶│ pipeline/     │
│ source       │  (live, per  │  (Playwright,      │  data/raw/     │ clean.py      │
│ adapters     │   cycle)     │   rate-limited)     │                │ + dedupe.py   │
└────────────┘               └──────────────────┘                └──────┬───────┘
                                                                          │ cleaned
                                                                   ┌──────▼───────┐
                                                                   │ SQLite         │
                                                                   │ fare_quotes,   │
                                                                   │ route_weights, │
                                                                   │ compliance_log,│
                                                                   │ index_values   │
                                                                   └──────┬───────┘
                                            ┌─────────────────────┐      │
                                            │ index/construct.py   │◀─────┤
                                            │ (Laspeyres/Paasche/  │      │
                                            │  Fisher)              │      │
                                            └──────────┬───────────┘      │
                                                        │                 │
                                            ┌───────────▼───────────┐     │
                                            │ FastAPI (app/main.py)  │◀────┘
                                            │ /api/index, /fares,    │
                                            │ /routes, /compliance,  │
                                            │ /elasticity, /heatmap  │
                                            └───────────┬───────────┘
                                                         │ JSON
                                            ┌───────────▼───────────┐
                                            │ React/Vite dashboard    │
                                            │ (frontend/)              │
                                            └───────────────────────┘
```

## Why these choices

- **SQLite via SQLAlchemy** — zero setup for a prototype, fully
  inspectable with any SQLite browser, and the ORM models
  (`app/db/models.py`) map directly onto Postgres if this needs to scale;
  no code above the session layer would need to change.
- **Playwright over `requests`/Scrapy alone** — every target site is a
  JS-rendered SPA (React). Playwright drives an actual headless browser,
  so the scraper sees what a real visitor's browser renders, including
  client-side validation state, rather than trying to reverse-engineer
  minified bundle internals.
- **Compliance gate as a first-class module, not a config flag** —
  `app/scraper/compliance.py` is invoked by the runner before any adapter
  touches its target, fetches the *live* robots.txt (cached 1h), and logs
  every decision. See `docs/ethics_compliance.md` for what it found.
- **SQLAlchemy models keep provenance** — every `FareQuote` row carries
  `source_id`, `scrape_run_id`, and `raw_snapshot_path`, so any number in
  the index can be traced back to the exact scrape run and raw JSONL
  snapshot it came from (`data/raw/run{N}_{source}.jsonl`).
- **One external scheduled task drives daily collection, not two
  uncoordinated triggers** — this used to also run an in-process
  APScheduler job inside the FastAPI process, on the theory that a
  long-running deployment would "self-sustain." In practice that process
  is *not* long-running (dev sessions end, the server restarts often), so
  it mostly sat dormant while still being a real risk on the occasions it
  did fire: two independent schedulers writing to the same SQLite file
  with no coordination between them is exactly the kind of thing that
  causes `database is locked` errors and silently-lost scrape runs. It was
  removed in favor of a single registered scheduled task (see the
  project's task runner) as the one source of truth, backed by:
  - **WAL mode + a busy_timeout pragma** (`app/db/session.py`) so a
    reader (the API) and a writer (a scrape) don't block each other, and a
    transient lock retries instead of raising immediately.
  - **An advisory file lock** (`app/lockfile.py`) around every `run-once`
    invocation, so even a manual run and the scheduled run overlapping by
    accident refuses the second one loudly instead of corrupting data.
  - **Crash-resilient scrape runs** (`app/scraper/runner.py`) — a
    `ScrapeRun` row is committed the moment a cycle starts, each source's
    data is cleaned and committed right after that source finishes rather
    than batched with everyone else at the end, and any exception that
    still escapes is caught, recorded on the run as `status="error"` with
    the real error message, and only then re-raised. Before this, *any*
    uncaught exception anywhere in a cycle rolled back the entire
    transaction — including the `ScrapeRun` row itself — leaving zero
    trace that a run was ever attempted. This was the most likely
    explanation for the scheduled task's `lastRunAt` updating with no
    corresponding new data some days.

## Directory map

```
backend/app/
  config.py            route basket, AP windows, source registry, travel-
                         spike calendar, MoSPI CPI reference, plausibility
                         bounds — the one place tunable policy constants live
  lockfile.py            advisory file lock guarding concurrent scrapes
  db/                   models.py (ORM), session.py (WAL + busy_timeout)
  regulator/
    auth.py              shared-token gate for the regulator surface (fails
                           closed; prototype-grade, not identity — see
                           docs/regulator_flagging_methodology.md)
    notice_draft.py      builds a DRAFT evidence document for one flag.
                           Produces documents only; nothing in this package
                           sends anything to anyone, by design
  scraper/
    compliance.py        robots.txt gate (wildcard-aware, fails closed)
    ratelimit.py          per-domain token bucket
    base.py                SourceAdapter interface, RawQuote, CaptchaDetected
    sources/                one adapter per named source
    registry.py             source_id -> adapter class
    runner.py                orchestrates one full scrape cycle; commits
                               incrementally per source and records a
                               status="error" run rather than losing data
  pipeline/
    dedupe.py             within-run duplicate removal
    clean.py               outlier flagging (statistical + plausibility
                             bounds), fare decomposition, per-row-resilient
                             persistence
  index/
    weights.py             DGCA CSV -> route weights
    construct.py            Laspeyres/Paasche/Fisher
    elasticity.py            lead-time curve
    booking_advice.py        "best time to book" verdict for one route
    date_watch.py             real-price tracker for one exact travel date
    spike_watch.py            festival/wedding-season price comparison
    cpi_divergence.py         APIx movement vs. the last published MoSPI CPI
  backtest/run_backtest.py  honest N-day backtest report
  routers/                  FastAPI routes
  cli.py                      manual operator commands (see `--help`;
                                run-once now takes the advisory lock and
                                exits non-zero if one's already held)
frontend/src/
  api.ts                     typed fetch client
  components/                 TabNav, HeroStat, CpiDivergence, TrendChart,
                                DateWatch, SpikeWatch, RouteFilter,
                                BookingAdvice, SectorHeatmap, ElasticityChart,
                                DataSources, FaresTable, KpiCards, Footer
  App.tsx                     tabbed dashboard shell (Overview / Track a
                                Trip / Festival Watch / Explore Routes /
                                Data Sources)
data/
  reference/                  real DGCA traffic CSV + provenance README
  raw/                        raw per-run JSONL snapshots (audit trail)
  airfare.db                  SQLite database (WAL mode: also airfare.db-wal/-shm)
  scrape.lock                 advisory lock file, present only mid-scrape
```
