from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class RouteOut(BaseModel):
    id: int
    origin: str
    destination: str
    display_name: str
    latest_weight: float | None = None


class FareQuoteOut(BaseModel):
    id: int
    route: str
    carrier_code: str
    source_id: str
    ap_window_days: int
    search_date: dt.date
    travel_date: dt.date
    fare_class: str
    base_fare: float | None
    taxes_fees: float | None
    total_fare: float | None
    is_outlier: bool
    sold_out: bool


class IndexPointOut(BaseModel):
    date: dt.date
    laspeyres: float
    paasche: float
    fisher: float
    sample_size: int
    routes_covered: int


class ComplianceStatusOut(BaseModel):
    source_id: str
    name: str
    kind: str
    domain: str
    allowed: bool | None
    reason: str | None
    checked_at: dt.datetime | None


class ElasticityPointOut(BaseModel):
    ap_window_days: int
    mean_fare: float
    min_fare: float
    max_fare: float
    sample_size: int
    elasticity_vs_prev: float | None = None


class MospiCpiReferenceOut(BaseModel):
    series_base: str
    reference_month: str
    reference_month_label: str
    published_date: dt.date
    next_release_date: dt.date
    headline_cpi_index: float
    headline_cpi_yoy_pct: float
    transport_division_index: float
    transport_division_yoy_pct: float
    passenger_transport_index: float
    passenger_transport_yoy_pct: float
    source_url: str
    source_note: str


class CpiDivergenceOut(BaseModel):
    has_signal: bool
    alert: bool
    message: str
    apix_change_pct: float | None = None
    apix_days_tracked: int | None = None
    apix_first_date: dt.date | None = None
    apix_last_date: dt.date | None = None
    ratio_vs_official_yoy: float | None = None
    mospi: MospiCpiReferenceOut


class SpikeCalendarWindowOut(BaseModel):
    key: str
    name: str
    start: dt.date
    end: dt.date
    why: str
    in_scraping_horizon: bool


class RouteSpikeSignalOut(BaseModel):
    route: str
    window_key: str
    window_name: str
    spike_mean_fare: float
    baseline_mean_fare: float
    pct_change: float
    spike_sample_size: int
    baseline_sample_size: int


class SpikeWatchOut(BaseModel):
    as_of: dt.date
    calendar: list[SpikeCalendarWindowOut]
    route_signals: list[RouteSpikeSignalOut]


class FestivalRoutePriceOut(BaseModel):
    route: str
    price: float
    is_estimated: bool
    sample_size: int
    confidence: str | None = None
    basis: str | None = None
    range_low: float | None = None
    range_high: float | None = None
    baseline_price: float | None = None
    baseline_is_estimated: bool = False
    baseline_sample_size: int = 0
    pct_change: float | None = None


class FestivalRoutePricesOut(BaseModel):
    window_key: str
    window_name: str
    start: dt.date
    end: dt.date
    why: str
    routes: list[FestivalRoutePriceOut]


class DateWatchCheckpointOut(BaseModel):
    ap_window_days: int
    checkpoint_date: dt.date
    status: str
    mean_fare: float | None = None
    min_fare: float | None = None
    sample_size: int
    is_estimated: bool = False
    confidence: str | None = None
    basis: str | None = None
    range_low: float | None = None
    range_high: float | None = None


class DateWatchOut(BaseModel):
    travel_date: dt.date
    checkpoints: list[DateWatchCheckpointOut]
    has_signal: bool
    message: str
    cheapest_so_far: DateWatchCheckpointOut | None = None
    priciest_so_far: DateWatchCheckpointOut | None = None
    gap_pct: float | None = None


class PriceGridCellOut(BaseModel):
    route: str
    ap_window_days: int
    mean_fare: float
    sample_size: int
    is_estimated: bool
    confidence: str | None = None
    basis: str | None = None
    range_low: float | None = None
    range_high: float | None = None


class PriceGridOut(BaseModel):
    cells: list[PriceGridCellOut]
    reference_window_days: int | None = None
    total_cells: int
    real_cells: int
    estimated_cells: int


class RouteAffordabilityOut(BaseModel):
    route: str
    origin: str
    destination: str
    distance_km: float
    mean_fare: float
    cheapest_fare: float
    sample_size: int
    cost_per_km: float
    wage_days_male_casual_labour: float
    wage_days_female_casual_labour: float


class WageReferenceOut(BaseModel):
    report_label: str
    survey_period: str
    published_date: dt.date
    casual_labour_daily_wage_male_inr: float
    casual_labour_daily_wage_female_inr: float
    regular_salaried_monthly_earnings_male_inr: float
    regular_salaried_monthly_earnings_female_inr: float
    self_employed_monthly_earnings_male_inr: float
    self_employed_monthly_earnings_female_inr: float
    source_url: str
    source_note: str


class AffordabilityReportOut(BaseModel):
    routes: list[RouteAffordabilityOut]
    cheapest_per_km_route: str | None = None
    most_expensive_per_km_route: str | None = None
    cost_per_km_gap_pct: float | None = None
    wage_reference: WageReferenceOut


class BookingAdviceOut(BaseModel):
    has_signal: bool
    verdict: str | None = None
    message: str
    cheapest_window_days: int | None = None
    cheapest_mean_fare: float | None = None
    priciest_window_days: int | None = None
    priciest_mean_fare: float | None = None
    gap_pct: float | None = None
    windows_with_data: int
    confidence: str | None = None


class PriceHistoryPointOut(BaseModel):
    search_date: dt.date
    cheapest_fare: float
    mean_fare: float
    sample_size: int


class RoutePriceHistoryOut(BaseModel):
    route: str
    days_of_history: int
    points: list[PriceHistoryPointOut]
    typical_low: float | None = None
    typical_high: float | None = None
    lowest_seen: float | None = None
    highest_seen: float | None = None
    latest_cheapest_fare: float | None = None
    latest_search_date: dt.date | None = None
