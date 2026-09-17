# API reference

FastAPI serves interactive OpenAPI docs at `/docs` (Swagger UI) and
`/redoc` once running (`uvicorn app.main:app`). This is the plain-text
summary for quick reference — the kind of API an NSO/RBI consumer could
build a monitoring feed against.

| Method & path | Purpose |
|---|---|
| `GET /health` | Liveness check |
| `GET /api/routes` | Basket routes with their latest DGCA-derived weight |
| `GET /api/compliance` | Live per-source robots.txt compliance status + reason |
| `GET /api/index/daily` | Daily Laspeyres/Paasche/Fisher index values, sample size, routes covered |
| `GET /api/index/backtest?method=fisher` | Honest N-day backtest report (see `docs/methodology.md`) |
| `GET /api/fares?origin=&destination=&ap_window_days=&source_id=&include_outliers=&limit=` | Filtered cleaned fare observations |
| `GET /api/elasticity?route_id=` | Lead-time elasticity curve (basket-wide if `route_id` omitted) |
| `GET /api/heatmap` | Mean/min fare per route × AP-window cell, for the dashboard heatmap |
| `GET /api/index/by-carrier` | Each carrier's own index series alongside the headline (see `docs/financial_context_methodology.md`) |
| `GET /api/carriers/financial-context` | Publicly disclosed quarterly revenue/profit/margin per carrier, or an honest "not available" reason |

## Regulator endpoints

See `docs/regulator_flagging_methodology.md` for the detection method and the
boundaries this surface deliberately does not cross. Endpoints marked **token**
require an `X-Regulator-Token` header matching the server's
`REGULATOR_ACCESS_TOKEN`; they return **503** when no token is configured (failing
closed) and **401** when one is configured but not matched.

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /api/regulator/flags?status_filter=&route_id=&carrier_code=` | public | Real fares flagged as statistically and materially elevated vs. their own history |
| `GET /api/regulator/flags/{id}` | public | One flag plus its live, individually-cited `possible_factors` |
| `PATCH /api/regulator/flags/{id}/review` | **token** | Record a human decision — `reviewed` or `dismissed` only |
| `GET /api/regulator/flags/{id}/draft-notice` | **token** | DRAFT evidence document for a human to review; sends nothing |
| `POST /api/regulator/citizen-reports` | public | Open intake for an unverified public fare report |
| `GET /api/regulator/citizen-reports/count` | public | Aggregate counts only (no content, no contact details) |
| `GET /api/regulator/citizen-reports` | **token** | Full report list for triage |
| `PATCH /api/regulator/citizen-reports/{id}/review` | **token** | Mark a report reviewed |

All responses are JSON; models are defined in `backend/app/schemas.py`
(Pydantic), which is also what generates the OpenAPI schema.
