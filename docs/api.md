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

All responses are JSON; models are defined in `backend/app/schemas.py`
(Pydantic), which is also what generates the OpenAPI schema.
