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

## Regulator access is role-based

The gated endpoints require a signed-in account with the `regulator` role. This
replaced an earlier single shared token, and the difference is not cosmetic: a
shared secret proved only that the caller held it, so every reviewer was
indistinguishable from every other one and `reviewed_by` could not be more than
free text. It is now taken from the session and written server-side — the API
rejects a `reviewed_by` supplied in the request body — so the review trail is an
actual record of who decided what.

Passwords are hashed with scrypt (`backend/app/auth/passwords.py`); sessions are
HMAC-signed bearer tokens with a working-day lifetime
(`backend/app/auth/tokens.py`). Every request re-reads the account from the
database and decides from that row, so deactivating an account or changing its
role takes effect on the next request rather than at token expiry.

What this still does **not** provide, stated plainly:

- **No per-token revocation.** Tokens are stateless; nothing records which ones
  exist. Deactivating the account works immediately, but a single leaked token
  cannot be invalidated on its own before it expires.
- **No password reset, lockout, or second factor.** There is no self-service
  recovery flow, no throttle on repeated failed logins beyond what one process
  gives you, and no MFA.
- **Not an identity provider.** A deployment holding real regulator credentials
  should put one in front of this.

### What is and isn't gated, and why

| Surface | Access | Reasoning |
|---|---|---|
| Flag list & detail | Government | A flag names a carrier, a route and a date. However carefully it is labelled a statistical observation, published openly it reads as an accusation and would be quoted as one — that judgement belongs with a human regulator before it goes anywhere |
| Review / dismiss a flag | Government | An open endpoint letting anyone mark a flag "dismissed" would make the review state meaningless |
| Draft notice | Government | Designed to read as a serious evidence packet; public access invites it circulating out of context |
| Raw citizen-report list | Government | May carry an optional contact email, and these are unverified — publishing them risks both a privacy leak and unverified claims being read as verified |
| A carrier's own flags, and responding to them | Airline (own carrier only) | The carrier a flag names can read it and put its account on the record before a human decides anything. Due process, not disclosure — no airline sees another's |
| Submit a fare report | Any signed-in account | An unauthenticated write endpoint feeding a human triage queue is an invitation to flood it; tying each report to an account makes a spammer identifiable and their reports removable as a set |
| The report count | Public | Aggregate only — carries no content or contact details, so the backlog stays honestly visible on the public report page |
| Index, routes, affordability, festival watch, per-carrier index, compliance | Public | The transparency half of the project. Reading never needs an account |

### The airline's right of reply

A flagged carrier can file a written response to a flag raised against it, which
the reviewing official sees alongside the flag. This follows directly from what a
flag is: a real fare plus a statistical annotation, explicitly **not** a finding
of wrongdoing. Letting the subject answer before a human acts is part of that
boundary rather than a courtesy feature.

An operator can write only the response text. It cannot change a flag's status,
its review note, or any measured value — answering a flag is a right of reply,
not the power to close it. The response is displayed as the carrier's own
unverified account, never merged into the measured data, for the same reason
citizen reports are kept separate.

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
