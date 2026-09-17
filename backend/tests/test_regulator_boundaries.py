"""Structural guard on the two promises this feature makes.

The regulator feature rests on two boundaries that are easy to state and
easy to erode later by accident:

  1. **No fairness verdict.** The system reports a real fare, the real
     baseline it departed from, and real dated context. It never computes
     whether that fare was fair, justified, or excessive. (Same rule
     test_financial_context.py already enforces for the financial-context
     feature; this extends it to flags and notices.)
  2. **No autonomous dispatch.** Nothing sends anything to an airline or
     any third party. Draft notices are documents produced for a human to
     act on through their own official channels.

A comment saying so is not enforcement. These tests fail the build if any
function, class, schema field, or actual API response key in the feature
starts to look like either boundary has slipped — including a flag ever
gaining a "sent" state.
"""
from __future__ import annotations

import datetime as dt
import inspect

from app import schemas
from app.db.models import CitizenFareReport, RegulatorFareFlag
from app.index import anomaly_detection
from app.regulator import auth, notice_draft
from app.routers import regulator

# "verdict" alone is deliberately not banned: app.index.booking_advice uses it
# legitimately for booking-timing advice ("book_early"/"can_wait"), which is a
# different thing entirely from a judgement about a carrier's pricing.
BANNED_VERDICT_FRAGMENTS = (
    "justif",
    "is_fair",
    "unfair",
    "fairness",
    "gouging",
    "price_verdict",
    "overcharg",
    "violation",
)

BANNED_AUTODISPATCH_FRAGMENTS = (
    "auto_send",
    "autosend",
    "send_notice",
    "dispatch_notice",
    "notify_airline",
    "email_airline",
    "notice_sent",
    "was_sent",
    "auto_dispatch",
    "webhook",
    "smtp",
    "sendmail",
)

ALL_BANNED = BANNED_VERDICT_FRAGMENTS + BANNED_AUTODISPATCH_FRAGMENTS

FEATURE_MODULES = (anomaly_detection, auth, notice_draft, regulator)

NO_ROBOTS_RESTRICTION = "User-agent: *\nAllow: /\n"


def _defined_names(module) -> list[str]:
    return [
        name
        for name, obj in inspect.getmembers(module)
        if (inspect.isfunction(obj) or inspect.isclass(obj))
        and getattr(obj, "__module__", None) == module.__name__
    ]


def _assert_clean(label: str, text: str) -> None:
    lowered = text.lower()
    for fragment in ALL_BANNED:
        assert fragment not in lowered, (
            f"{label} matches banned fragment {fragment!r} — this feature must never compute a "
            f"fairness verdict on a fare, nor send anything to an airline. Return the real "
            f"numbers and let a human decide (see app.regulator.notice_draft's docstring)."
        )


def test_no_function_or_class_name_crosses_either_boundary():
    for module in FEATURE_MODULES:
        for name in _defined_names(module):
            _assert_clean(f"{module.__name__}.{name}", name)


def test_no_module_level_callable_or_constant_name_crosses_either_boundary():
    for module in FEATURE_MODULES:
        for name in vars(module):
            if name.startswith("_"):
                continue
            _assert_clean(f"{module.__name__}.{name}", name)


def test_no_schema_field_crosses_either_boundary():
    schema_names = [
        "RegulatorFlagOut",
        "RegulatorFlagDetailOut",
        "RegulatorFlagReviewIn",
        "DraftNoticeOut",
        "CitizenFareReportIn",
        "CitizenFareReportOut",
        "CitizenReportReviewIn",
        "CitizenReportCountOut",
    ]
    for schema_name in schema_names:
        model = getattr(schemas, schema_name)
        for field_name in model.model_fields:
            _assert_clean(f"{schema_name}.{field_name}", field_name)


def test_no_db_column_crosses_either_boundary():
    for model in (RegulatorFareFlag, CitizenFareReport):
        for column in model.__table__.columns:
            _assert_clean(f"{model.__name__}.{column.name}", column.name)


def test_a_flag_can_never_be_marked_sent():
    # The review endpoint's allowed set is the only way a flag's status
    # changes. If "sent" (or any dispatch-shaped state) ever appears here,
    # this feature has started claiming it issued something.
    assert regulator.ALLOWED_REVIEW_STATUSES == {"reviewed", "dismissed"}
    assert regulator.ALLOWED_REPORT_STATUSES == {"reviewed"}
    for allowed in regulator.ALLOWED_REVIEW_STATUSES | regulator.ALLOWED_REPORT_STATUSES:
        _assert_clean(f"allowed status {allowed!r}", allowed)
        assert allowed != "sent"


def test_no_outbound_send_capability_is_imported_anywhere_in_the_feature():
    # A send capability has to come from somewhere. If one of these ever
    # appears in the feature's imports, the boundary has been crossed in
    # code even if every name still looks innocent.
    forbidden_modules = {"smtplib", "email.message", "sendgrid", "boto3", "twilio"}
    for module in FEATURE_MODULES:
        source = inspect.getsource(module)
        for forbidden in forbidden_modules:
            assert f"import {forbidden}" not in source, (
                f"{module.__name__} imports {forbidden} — this feature sends nothing to anyone"
            )


def _walk_keys(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield str(key)
            yield from _walk_keys(value)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _walk_keys(item)


def test_real_runtime_output_of_every_public_surface_is_clean(session, monkeypatch):
    """The name checks above can be satisfied while a dict literal quietly
    adds a banned key, so this walks the actual output too."""
    monkeypatch.setattr(
        "app.scraper.compliance.requests.get",
        lambda *a, **k: type("R", (), {"status_code": 200, "text": NO_ROBOTS_RESTRICTION})(),
    )
    monkeypatch.setattr("app.news.fetch_news._cache", {})
    monkeypatch.setattr(
        "app.news.fetch_news._fetch_all",
        lambda gate: type(
            "R",
            (),
            {"items": [], "as_of": dt.datetime.now(dt.timezone.utc), "sources_checked": []},
        )(),
    )

    from app.db.models import Carrier, FareQuote, Route

    route = Route(origin="DEL", destination="BOM", display_name="Delhi-Mumbai")
    session.add(route)
    session.add(Carrier(code="SG", name="SpiceJet"))
    session.commit()

    day = dt.date(2026, 11, 1)
    quote = FareQuote(
        route_id=route.id,
        carrier_code="SG",
        source_id="spicejet",
        ap_window_days=7,
        search_date=dt.datetime.combine(day, dt.time.min),
        travel_date=dt.datetime.combine(day + dt.timedelta(days=7), dt.time.min),
        fare_class="economy",
        total_fare=21000.0,
        is_outlier=False,
        sold_out=False,
        scraped_at=dt.datetime.utcnow(),
    )
    session.add(quote)
    session.commit()

    flag = RegulatorFareFlag(
        route_id=route.id,
        carrier_code="SG",
        ap_window_days=7,
        flagged_search_date=dt.datetime.combine(day, dt.time.min),
        flagged_travel_date=dt.datetime.combine(day + dt.timedelta(days=7), dt.time.min),
        fare_quote_id=quote.id,
        observed_fare=21000.0,
        baseline_median_fare=7025.0,
        baseline_mad=75.0,
        robust_z_score=125.6,
        pct_above_baseline_median=198.9,
        baseline_sample_size=4,
        status="new",
        detected_at=dt.datetime.utcnow(),
    )
    session.add(flag)
    session.commit()

    draft = notice_draft.build_draft_notice(session, flag)
    factors = anomaly_detection.why_context_for_flag(
        session,
        carrier_code="SG",
        flagged_travel_date=day + dt.timedelta(days=7),
        flagged_search_date=day,
    )

    for key in _walk_keys(draft):
        _assert_clean(f"draft-notice output key {key!r}", key)
    for key in _walk_keys(factors):
        _assert_clean(f"possible_factors output key {key!r}", key)


def test_the_draft_notice_states_its_own_limits_in_its_text():
    # Not a naming check — the document's own body must carry the boundary,
    # because the document is the thing a human might forward onward.
    assert "DRAFT" in notice_draft.DRAFT_DISCLAIMER
    assert "no legal or regulatory authority" in notice_draft.DRAFT_DISCLAIMER
    assert "issues nothing and sends nothing" in notice_draft.BOUNDARY_NOTICE
    assert "no finding" in notice_draft.BOUNDARY_NOTICE.lower()
