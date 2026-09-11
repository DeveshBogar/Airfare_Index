from __future__ import annotations

import datetime as dt

from app.db.models import FareQuote
from app.pipeline.clean import _get_or_create_route, clean_and_store, decompose_fare, is_plausible_fare, robust_outlier_mask
from app.pipeline.dedupe import dedupe_raw_quotes
from app.scraper.base import RawQuote
from app.scraper.sources.gated_generic import parse_airline_fare_text, parse_ota_fare_text


def test_get_or_create_route_treats_both_directions_as_the_same_route(session):
    # a route searched as DEL->BOM one day and BOM->DEL another (e.g. after
    # config.ROUTE_BASKET's declared order changed) must resolve to one
    # Route row, not fragment into "Delhi-Mumbai" and "Mumbai-Delhi"
    forward = _get_or_create_route(session, "DEL", "BOM")
    reverse = _get_or_create_route(session, "BOM", "DEL")
    assert forward.id == reverse.id


def _q(total_fare, fare_class="economy"):
    return RawQuote(
        origin="DEL",
        destination="BOM",
        carrier_code="SG",
        ap_window_days=7,
        search_date=dt.date(2026, 9, 4),
        travel_date=dt.date(2026, 9, 11),
        fare_class=fare_class,
        total_fare=total_fare,
    )


def test_dedupe_drops_exact_duplicates_within_a_batch():
    quotes = [_q(7085), _q(7085), _q(8310)]
    result = dedupe_raw_quotes(quotes)
    assert len(result) == 2


def test_dedupe_keeps_distinct_fare_classes():
    quotes = [_q(7085, "spicesaver"), _q(7085, "spiceflex")]
    assert len(dedupe_raw_quotes(quotes)) == 2


def test_robust_outlier_mask_flags_extreme_value():
    values = [7000, 7100, 6900, 7050, 45000]  # last one is way off
    mask = robust_outlier_mask(values)
    assert mask == [False, False, False, False, True]


def test_robust_outlier_mask_skips_small_groups():
    # fewer than MIN_GROUP_SIZE_FOR_OUTLIER_CHECK points -> nothing flagged,
    # not enough data to know what "normal" looks like yet
    values = [7000, 45000]
    assert robust_outlier_mask(values) == [False, False]


def test_robust_outlier_mask_handles_identical_values():
    values = [7000, 7000, 7000, 7000]
    assert robust_outlier_mask(values) == [False, False, False, False]


def test_decompose_fare_passes_through_when_both_present():
    base, tax = decompose_fare(1000, 800, 200)
    assert (base, tax) == (800, 200)


def test_decompose_fare_derives_missing_component():
    base, tax = decompose_fare(1000, 800, None)
    assert (base, tax) == (800, 200)


def test_decompose_fare_leaves_null_when_source_gives_only_total():
    # this is the real situation for SpiceJet/Akasa today — never fabricate
    # a split when the source doesn't expose one
    base, tax = decompose_fare(7085, None, None)
    assert (base, tax) == (None, None)


def test_is_plausible_fare_accepts_real_range():
    assert is_plausible_fare(7085) is True
    assert is_plausible_fare(500) is True  # inclusive lower bound
    assert is_plausible_fare(100_000) is True  # inclusive upper bound


def test_is_plausible_fare_rejects_scraper_bug_shaped_values():
    assert is_plausible_fare(0) is False
    assert is_plausible_fare(5) is False  # e.g. a seat count misread as a price
    assert is_plausible_fare(9_999_999) is False


def test_clean_and_store_skips_one_bad_row_but_keeps_the_rest(session):
    good_1 = _q(7085)
    bad = _q(6500)
    bad.carrier_code = None  # forces a NOT NULL failure for just this row
    good_2 = _q(8310)

    inserted = clean_and_store(session, run_id=1, raw_quotes=[good_1, bad, good_2])

    assert inserted == 2
    stored_fares = {q.total_fare for q in session.query(FareQuote).all()}
    assert stored_fares == {7085, 8310}


def test_clean_and_store_flags_an_implausible_fare_as_outlier(session):
    quote = _q(15)  # far below PLAUSIBLE_FARE_INR_RANGE - a scraper-bug shape, not a real fare
    clean_and_store(session, run_id=1, raw_quotes=[quote])
    stored = session.query(FareQuote).one()
    assert stored.is_outlier is True
    assert stored.total_fare == 15


AIRLINE_FIXTURE_TEXT = """
09:55
DEL
Flight Details
2h 30m
12:25
BOM
6E 2134
Direct
₹ 7,200
"""

OTA_FIXTURE_TEXT = """
6E-2134   DEL -> BOM   ₹ 7,200
AI 665    DEL -> BOM   ₹ 8,450
QP 1119   DEL -> BOM   ₹ 6,530
"""


def test_parse_airline_fare_text_extracts_rows():
    rows = parse_airline_fare_text(AIRLINE_FIXTURE_TEXT, "6E")
    assert rows == [{"carrier_code": "6E", "flight_no": "6E 2134", "total_fare": 7200.0}]


def test_parse_ota_fare_text_extracts_multiple_carriers():
    rows = parse_ota_fare_text(OTA_FIXTURE_TEXT)
    carriers = {r["carrier_code"] for r in rows}
    assert carriers == {"6E", "AI", "QP"}
    assert len(rows) == 3
