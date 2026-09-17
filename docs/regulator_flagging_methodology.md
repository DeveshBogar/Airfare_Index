# Regulator flagging methodology

## What this feature adds

Four things, in the order a regulator would actually use them:

1. **Automated fare-anomaly flagging** (`app/index/anomaly_detection.py`) —
   every daily run tests each route+carrier+booking-window's newest real fare
   against that same group's own prior real days, and records a flag when it comes
   in both statistically unusual *and* materially higher.
2. **Real, dated "why" context** — each flag carries the festival-demand window it
   falls in (if any), any airfare-relevant news published in the week before it, and
   the carrier's own last publicly disclosed net margin. All three are real, dated,
   and cited; none is combined into a score.
3. **Draft notices** (`app/regulator/notice_draft.py`) — a structured evidence
   document for one flag, for a human regulator to read, judge, and act on through
   their own channels.
4. **Citizen fare reports** (`POST /api/regulator/citizen-reports`) — an open
   intake for members of the public, kept strictly separate from the system's own
   verified data.

## The detection test

For one `(route, carrier, advance-purchase window)`, the representative price on a
day is the **cheapest real (non-outlier, non-sold-out, priced) fare** collected that
day — the same rule `docs/methodology.md` sets for the index itself.

The newest day is tested against every earlier real day in the same group:

```
baseline_median = median(prior real daily fares)
baseline_mad    = median(|fare − baseline_median|)          # median absolute deviation
z               = 0.6745 × (observed − baseline_median) / baseline_mad

flag when   z > 3.5   AND   observed ≥ baseline_median × 1.15
```

Nothing here is a new invention. `app/pipeline/clean.py::robust_outlier_mask`
already screens scraped data with exactly this median/MAD z-score and exactly this
3.5 cutoff (the Iglewicz & Hoaglin 1993 convention), within one scrape run across
carriers. This module reuses the same formula and the same constants along a
different axis — across days, for one fixed group — with three deliberate
differences:

- **Directional.** `clean.py` takes `abs(z)`, since a parsing bug can produce an
  absurdly low value as easily as a high one. Here a fare *below* its own history is
  a bargain, not a regulatory concern, so only the elevated side is ever flagged.
- **Today only.** Only the newest real day in a group is tested. A daily run asks
  one question — "is today unusual for this group?" — and never retroactively
  re-flags days already assessed. `--backfill` exists to assess history collected
  before the feature existed.
- **A materiality floor.** `MIN_PCT_ABOVE_BASELINE_FOR_FLAG = 15%`, required *in
  addition* to the z-score. The z-score alone is necessary but not sufficient,
  because on a route whose fares barely move the MAD is tiny and a trivial increase
  scores enormously. This is not hypothetical: on this project's own collected data,
  Delhi–Srinagar (SpiceJet, T+7) scored **z = 22.9 on a fare just 8.0% above its
  baseline**. Statistically unusual for that route — yes. Worth a regulator's
  limited attention — no. A queue full of 8% flags teaches its user to ignore the
  queue, which is worse than having no queue. 15% sits well below the genuinely
  serious cases the same data surfaced (Mumbai–Delhi at +230%, Kolkata–Delhi at
  +82%), so real problems still surface early.

No flag is raised when a group has fewer than 4 prior real days
(`MIN_HISTORY_DAYS_FOR_ANOMALY_CHECK`, mirroring `clean.py`'s own minimum), or when
the baseline has zero spread — in both cases "normal" isn't yet knowable, and a
flag would be noise dressed as signal.

### Known limitation

Median/MAD is robust to a *minority* of elevated days by design. The same property
means a **sustained** elevated-fare period gradually gets absorbed into the baseline
and stops producing new flags. This detector catches departures from a route's own
recent norm; it is not a measure of a slow structural climb. The index trend,
CPI-divergence panel, and festival spike-watch already cover that ground, and this
limitation is stated in the module docstring too rather than left for a user to
discover.

## The three "why" sources

`why_context_for_flag()` returns a flat list of independent, individually-cited
items, drawn only from data this project already collects:

| Factor | Source | Already used by |
|---|---|---|
| Festival/wedding demand window | `app.config.spike_window_for_date` | `app/index/spike_watch.py` |
| Airfare-relevant news in the prior 7 days | `app.news.fetch_news` + `app.news.keywords.categorize` | the Overview news panel |
| Carrier's last disclosed net margin | `app.index.financial_context` | the financial-context panel |

These are **not** ranked, weighted, scored, or combined. A festival window, a
fuel-price story, and a quarterly margin are three separate real facts. Which — if
any — explains a given fare is a human judgement, made better by having all three
in hand and worse by having them mashed into a single number that implies a
confidence nobody has. News being unreachable degrades the context gracefully and
never removes the flag: the flag is built from fare data, the context is not the
finding.

## Correlation, never a verdict

**This system computes no judgement about whether any fare was fair, justified,
lawful, or excessive.** It reports: a real collected fare, the real baseline it
departed from, the stated method that identified it, and real dated factors that may
bear on it.

That restraint is not modesty, it's accuracy. A flag means one thing precisely: this
fare departed from its own group's recent history by more than the stated
thresholds. Entirely ordinary commercial factors — a demand surge, a fuel move, a
grounded aircraft, the last few seats on a full flight — can fully account for that.
The system cannot distinguish those from a pricing problem, so it does not pretend
to, and the draft notice says so in its own body text.

This mirrors the rule already enforced for the financial-context feature (see
`docs/financial_context_methodology.md`): a carrier's quarterly, network-wide margin
cannot validate or invalidate a single route's single-day fare either.

## Draft notices are human-in-the-loop, full stop

**Nothing in this feature sends anything to anyone.** There is no email function, no
webhook, no outbound request, and no "sent" state on a flag — its lifecycle is
`new → reviewed | dismissed` and nothing else.

The reason is straightforward: this project has no regulatory authority, no verified
identity of whoever is operating it, and no relationship with DGCA or MoCA. A
prototype that dispatched correspondence to an airline as though it did would be
misrepresenting itself. So the division of labour is explicit — **this system
produces evidence; a human decides and acts.** Every draft notice opens with:

> DRAFT — NOT AN OFFICIAL COMMUNICATION. Generated by a prototype statistical
> monitoring tool. Has not been reviewed, approved, or issued by any regulator, and
> carries no legal or regulatory authority. Must not be sent to any airline or third
> party as-is.

`backend/tests/test_regulator_boundaries.py` enforces both this and the
no-verdict rule structurally rather than by convention: it fails the build if any
function, class, schema field, DB column, or actual API response key in the feature
starts to look like autonomous dispatch or a fairness finding, if a dispatch-capable
library is ever imported into the feature, or if a flag ever gains a `sent` status.

## Regulator access is prototype-grade

The gated endpoints require a single shared token (`X-Regulator-Token`, configured
via the `REGULATOR_ACCESS_TOKEN` environment variable, never committed).

What it provides: the review actions, the draft-notice document, and the raw
citizen-report list aren't open to the public internet.

What it does **not** provide, stated plainly:

- **Not authentication.** It proves possession of a shared secret, not identity.
  Everyone holding the token is indistinguishable.
- **Not an audit trail.** `reviewed_by` is free text the reviewer types; the system
  cannot verify it.
- **Not authorization.** No roles, no scopes — the token opens every gated endpoint
  or none.

A real deployment would place a proper identity provider in front of this. It fails
**closed**: with no token configured, gated endpoints return 503 rather than falling
open, the same posture `app/scraper/compliance.py` takes when it cannot verify a
robots.txt.

### What is and isn't gated, and why

| Surface | Access | Reasoning |
|---|---|---|
| Flag list & detail | Public | Same real collected data the public dashboard already shows, plus a stated statistical annotation |
| Citizen-report count | Public | Honest visibility that reports exist and how many await review |
| Review / dismiss a flag | Token | An open endpoint letting anyone mark a flag "dismissed" would make the review state meaningless |
| Draft notice | Token | Designed to read as a serious evidence packet; public access invites it circulating out of context |
| Raw citizen-report list | Token | May carry an optional contact email, and these are unverified — publishing them risks both a privacy leak and unverified claims being read as verified |

## Citizen reports are unverified, and kept that way

`CitizenFareReport` has **no foreign key or any join path** to `RegulatorFareFlag`,
and origin/destination are stored as free text rather than resolved against the
tracked route basket. That separation is deliberate: blending self-reported claims
with collected data would let an unverified claim inherit the credibility of
verified data, which is exactly what this project's real-data-only rule exists to
prevent. A reviewer can read reports alongside the real flags; the data never
merges.

`contact_email` is the only PII field and is optional. The form asks for nothing
else and tells the submitter not to provide anything else.

## Provenance

Built on `app/index/carrier_index.py` and `app/index/financial_context.py` (see
`docs/financial_context_methodology.md`), whose real per-carrier and
financial-disclosure data supply part of the flag context.
