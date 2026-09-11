# APIx — Real-time Airfare Price Index for India

**Smart India Hackathon prototype** for augmenting the CPI's Transport &
Communication sub-group with a real-time, route-level airfare index built
from live-scraped carrier data — the problem MoSPI/NSO's manual
price-collection can't keep up with, since over 90% of Indian domestic
air tickets are now bought online at prices that swing 200–400% in a
single day.

## What's actually real here

This isn't a mockup with placeholder numbers. Specifically:

- **The route weights are computed from a real DGCA dataset** —
  `data/reference/dgca_city_pair_traffic.csv`, sourced from DGCA's own
  published city-pair passenger-traffic statistics (see
  [`data/reference/README.md`](data/reference/README.md) for exact
  provenance). Nothing about the weighting is hardcoded.
- **Every source named in the problem statement was checked against its
  live robots.txt before any scraper code was written** — see
  [`docs/ethics_compliance.md`](docs/ethics_compliance.md). Two sources
  (SpiceJet, Akasa Air) currently permit automated access and run live;
  the other nine have working, unit-tested adapters that are held behind
  a runtime compliance gate rather than scraping pages their operators
  have explicitly disallowed.
- **The scraper actually runs against the real internet** — SpiceJet and
  Akasa Air's live booking flows, collecting genuine current fares across
  the route basket and every advance-purchase window (T+1/7/15/30/45).
  Nothing in `fare_quotes` is synthetic.
- **The backtest reports its own real sample size honestly.** DGCA
  doesn't publish a fare time series to diff against (checked — only
  traffic and load-factor data), so instead of padding a fake 30-day
  chart, the backtest module says exactly how many real days of index
  history exist and grows that number every day the scheduler runs.

## The pieces, mapped to the problem statement

| Problem statement ask | Where |
|---|---|
| (a) Ethical, rate-limited, multi-source scraping engine | `backend/app/scraper/` — [`compliance.py`](backend/app/scraper/compliance.py), [`ratelimit.py`](backend/app/scraper/ratelimit.py), [`sources/`](backend/app/scraper/sources/) |
| (b) Cleaned, de-duplicated fare database with full metadata | `backend/app/pipeline/`, `backend/app/db/models.py` |
| (c) Index-construction module, routes/weights from DGCA data | `backend/app/index/` |
| (d) Interactive dashboard + API for NSO/RBI consumption | `frontend/`, `backend/app/routers/` |
| Documentation | `docs/` |
| Automated tests | `backend/tests/` (`pytest`) |
| 30-day backtest vs. DGCA data | `backend/app/backtest/run_backtest.py` — see honesty note above |

Full architecture diagram and design rationale: [`docs/architecture.md`](docs/architecture.md).
Index construction formulas: [`docs/methodology.md`](docs/methodology.md).
robots.txt audit and scraping ethics: [`docs/ethics_compliance.md`](docs/ethics_compliance.md).
API reference: [`docs/api.md`](docs/api.md).

## Quickstart

### Backend

```bash
cd backend
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt   # Windows; use bin/pip on macOS/Linux
./.venv/Scripts/python -m playwright install chromium
./.venv/Scripts/python ../scripts/download_dgca_data.py
./.venv/Scripts/python -m app.cli seed-dgca-weights
./.venv/Scripts/python -m app.cli run-once            # real live scrape, seeds fare_quotes
./.venv/Scripts/python -m app.cli build-index
./.venv/Scripts/python -m uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173, proxies /api to :8001
```

### Tests

```bash
cd backend
./.venv/Scripts/python -m pytest tests/ -v
```

## What's next for a production deployment

- Data-sharing / NDC API agreements with the nine gated sources (see
  `docs/ethics_compliance.md`) — the adapters are already written and
  tested; only the compliance gate needs their permission to flip on.
- Swap SQLite for Postgres (the ORM layer needs no changes).
- Proxy-pool / IP-rotation support is architected as a pluggable interface
  in the rate limiter but intentionally unused in this prototype — no
  paid proxy service was provisioned, and it isn't needed while operating
  within each site's own stated limits.
