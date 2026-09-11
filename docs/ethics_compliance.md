# Ethics & compliance

The problem statement requires the scraper to "handle JavaScript-rendered
pages, dynamic CAPTCHAs, anti-bot measures... while remaining compliant with
the robots.txt and terms of service of source websites, with appropriate
rate-limiting and ethical-scraping safeguards." This document is the audit
trail behind that requirement — what we checked, what it means for the
system's design, and how the code enforces it at runtime rather than by
one-time assumption.

## robots.txt audit (2026-09-04)

Every source named in the problem statement was checked directly against
its live, current robots.txt before any scraper code was written.

| Source | Domain | Search/booking path | Result |
|---|---|---|---|
| SpiceJet | www.spicejet.com | `/search` | **Allowed** — `Disallow:` list only covers `/cgi-bin/`, `/api/v1`, `/public/`, `/externalBooking` |
| Akasa Air | www.akasaair.com | `/flight-booking`, `/flight-search` | **Allowed** — robots.txt has no `Disallow` rules at all, only `Sitemap:` entries |
| IndiGo | www.goindigo.in | `/booking/*`, `/search.html` | **Blocked** — explicitly disallowed; the domain also rejects plain HTTP(S) requests outright (Akamai bot protection — even a robots.txt fetch times out with a non-browser client) |
| Air India | www.airindia.com | `/book/*` | **Blocked** — same Akamai-style protection prevents even fetching robots.txt with a plain HTTP client, so permission can't be verified; the compliance gate fails closed |
| Air India Express | www.airindiaexpress.com | `/flight-availability` | **Blocked** — explicitly disallowed |
| ixigo | www.ixigo.com | `/flights/search`, `/flights/review`, `/search/result/`, `/api/` | **Blocked** — explicitly disallowed |
| EaseMyTrip | www.easemytrip.com | `/flight-search/listing*` | **Blocked** — explicitly disallowed |
| Cleartrip | www.cleartrip.com | `/flights/search*` | **Blocked** — explicitly disallowed (general `Allow: /` doesn't cover it — the more specific `Disallow` wins) |
| Yatra | www.yatra.com | `/air/domestic-flight-listing` | **Blocked** — robots.txt unreachable via plain HTTP; gate fails closed |
| Goibibo | www.goibibo.com | `/flights/air-*` | **Blocked** — robots.txt unreachable via plain HTTP; gate fails closed |
| MakeMyTrip | www.makemytrip.com | `/flight/search` | **Blocked** — robots.txt unreachable via plain HTTP; gate fails closed |

**Practical result: 2 of 11 named sources currently permit automated
access to their search results — SpiceJet and Akasa Air.** Every other
source has adapter code written and unit-tested against fixture text (see
`backend/tests/test_clean.py`), but is held behind the compliance gate.

This is a real, load-bearing finding, not a formality: it directly shaped
which sources the system treats as "live" today. It's also not a
first-of-its-kind observation — DGCA's own Tariff Monitoring Unit "monitors
airfares on select domestic sectors on a random basis by using airlines'
websites on a monthly basis" (per the Ministry of Civil Aviation's public
statements), i.e. the government already does website-based fare
monitoring manually. A production deployment of this system would pursue
the same path the TMU implies for the blocked sources: a data-sharing
arrangement or an official API/NDC partnership, not a robots.txt override.

## How the gate works (not a one-time check)

`backend/app/scraper/compliance.py` fetches and parses each domain's
robots.txt at runtime, on every scrape cycle (cached for one hour to avoid
hammering the site with robots.txt requests), and only lets an adapter run
if every path it needs is currently permitted. Two implementation details
matter for correctness, not just intent:

- **Wildcard support.** Several of the audited files (ixigo, EaseMyTrip)
  use `*` and trailing `$` in their rules — syntax Python's stdlib
  `urllib.robotparser` does not support. The gate implements Google's
  de-facto robots.txt matching semantics (longest-match wins, `Allow`
  breaks ties) instead.
- **Fail closed.** If robots.txt can't be fetched at all (network error,
  5xx, or — as with IndiGo/Air India — the domain's bot protection blocks
  even a plain HTTP request), the source is treated as **not** allowed.
  Only an explicit 404 (no robots.txt published) is treated as "no
  restrictions stated," matching the de-facto standard.

Every decision, allowed or not, is logged to the `compliance_log` table
with the exact path checked and the matching rule, and surfaced live in
the dashboard's "Source compliance status" panel and the `/api/compliance`
endpoint — so the system's actual behavior is auditable, not just its
source code.

## Rate limiting, session behavior, and CAPTCHA handling

- **Rate limiting**: `backend/app/scraper/ratelimit.py` enforces a minimum
  6-second gap between any two requests to the same domain, shared across
  every route/window being collected — a full basket pass makes roughly
  one request every 6 seconds to a given site, not a burst.
- **Session/UA behavior**: each source gets its own fresh browser context
  with a realistic desktop UA drawn from a small pool
  (`app/config.USER_AGENT_POOL`). This is normal browser variation, not UA
  spoofing to defeat detection — the compliance gate is what governs
  whether we're allowed to be there at all, not the UA string.
- **CAPTCHA / bot-challenge handling**: `SourceAdapter.detect_captcha()`
  checks for common challenge markers (reCAPTCHA/hCaptcha iframes,
  Cloudflare's challenge page, PerimeterX). On detection the adapter raises
  `CaptchaDetected`, the runner logs it and backs off for the rest of that
  source's run. **The system never attempts to solve or bypass a
  challenge** — that would defeat the purpose of the compliance gate
  entirely, and it's a hard rule for this project regardless of what
  robots.txt says.
- **Reading, not probing**: adapters read what a normal visitor's browser
  would render for a permitted search page (SpiceJet: query-string search
  URL; Akasa: the real interactive form, city autocomplete and calendar
  included) rather than calling internal JSON APIs directly, even where
  robots.txt happens not to disallow them. Booking flows are never taken
  past reading the fare list — no seat selection, no passenger details, no
  payment step.

## A real operational finding worth recording

During development, Akasa Air's booking form (permitted by robots.txt)
intermittently kept its "Search Flights" button disabled after dozens of
rapid, back-to-back automated searches used to debug the adapter's
selectors — even though the exact same interaction sequence worked
correctly under normal-cadence use. This reads as a soft, behavioral
anti-automation defense (a debounced client-side validation state that
degrades under unusually rapid repeated use) distinct from robots.txt or a
hard CAPTCHA. It's a useful reminder that "permitted by robots.txt" isn't
the same as "safe to hit as fast as possible" — the production system's
real cadence (one pass per route/window per day via the scheduler, not
back-to-back debugging runs) is well below whatever threshold triggered
it, and the rate limiter keeps it that way.
