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
boundaries this surface deliberately does not cross. Endpoints marked **gov**
require a signed-in account with the `regulator` role: send the token from
`POST /api/auth/login` as `Authorization: Bearer <token>`. They return **401**
when nobody is signed in and **403** when the signed-in account has a different
role.

Flags are **not public**. A flag names a carrier, a route and a date, and
however carefully it is labelled as a statistical observation it would be
quoted as an accusation. Whether any of it warrants action is a human
regulator's judgement to make first, so the queue does not leave that desk.
The one exception is the named carrier itself, which reads and answers its own
flags through the operator endpoints below — due process, not disclosure.

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /api/regulator/flags?status_filter=&route_id=&carrier_code=` | **gov** | Real fares flagged as statistically and materially elevated vs. their own history |
| `GET /api/regulator/flags/{id}` | **gov** | One flag plus its live, individually-cited `possible_factors` |
| `PATCH /api/regulator/flags/{id}/review` | **gov** | Record a human decision — `reviewed` or `dismissed` only |
| `GET /api/regulator/flags/{id}/draft-notice` | **gov** | DRAFT evidence document for a human to review; sends nothing |
| `POST /api/regulator/citizen-reports` | signed in | Intake for an unverified public fare report — any role, but not anonymous |
| `GET /api/regulator/citizen-reports/count` | public | Aggregate counts only (no content, no contact details) |
| `GET /api/regulator/citizen-reports` | **gov** | Full report list for triage |
| `PATCH /api/regulator/citizen-reports/{id}/review` | **gov** | Mark a report reviewed |

## Authentication

**Reading needs no account.** Everything in the first table above, plus the
aggregate report count, is open to anyone. That is the point: the transparency
half of this project should not sit behind a login.

**Writing does.** Submitting a fare report requires a signed-in account of any
role. An unauthenticated write endpoint feeding a human triage queue is an open
invitation to flood it; tying each report to an account makes a spammer
identifiable and their reports removable as a set.

Three roles: `citizen` (a traveller — submits and follows fare reports),
`regulator` (government official) and `operator` (an airline, bound to one
carrier code). One login endpoint serves all three: the role lives on the
account, so a per-role form would only let a caller discover which role a
username has. See `backend/app/auth/roles.py`.

Accounts are provisioned with `python -m app.cli create-user` (or
`seed-demo-users`); there is deliberately no public registration endpoint,
because the right to review flags, or to answer on behalf of an airline, is not
something a visitor should be able to grant themselves.

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /api/auth/login` | public | Exchange username + password for a bearer token |
| `GET /api/auth/me` | signed in | The current account, used to restore a session on page load |
| `POST /api/auth/logout` | public | Client-side only — tokens are stateless, so there is nothing to revoke server-side |

### Who can reach what

| Surface | Traveller | Government | Airline |
|---|---|---|---|
| Index, routes, elasticity, heatmap, affordability, festival watch, per-carrier index, compliance, report count | yes (no account) | yes | yes |
| Submit a fare report, follow your own reports | needs a traveller account | yes | yes |
| Flag queue, review actions, draft notices, raw report list | no (401) | yes | no (403) |
| Own carrier's fares, index, flags, right of reply | no (401) | no (403) | own carrier only |

## Airline operator endpoints

Every endpoint below is scoped server-side to the signed-in operator's own
carrier. There is no carrier parameter anywhere in this router — taking the
scope from the session rather than the request makes the safe behaviour the
only behaviour available. A flag belonging to another carrier returns **404**
rather than 403, so an operator cannot map competitors' flags by walking the id
space.

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /api/operator/overview` | **airline** | Own carrier index, market headline, own fare/flag counts |
| `GET /api/operator/flags` | **airline** | Flags raised against this carrier only |
| `POST /api/operator/flags/{id}/response` | **airline** | File the airline's written account of a flagged fare |
| `GET /api/operator/fares?limit=` | **airline** | This carrier's own collected fares |

An operator writes only the response columns. It cannot change a flag's status,
review note, or any measured value: answering a flag is a right of reply, not
the ability to close it. The response is shown to the reviewing official
alongside the flag, and is labelled as the carrier's own unverified account.

## Traveller endpoints

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /api/citizen/my-reports` | signed in | Fare reports submitted by this account, and their triage status |

Filtered on the account id from the session, so it can only ever return the
caller's own reports.

All responses are JSON; models are defined in `backend/app/schemas.py`
(Pydantic), which is also what generates the OpenAPI schema.
