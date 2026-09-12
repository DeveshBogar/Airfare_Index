const BASE = "/api";

export interface RouteOut {
  id: number;
  origin: string;
  destination: string;
  display_name: string;
  latest_weight: number | null;
}

export interface IndexDailyPoint {
  date: string;
  sample_size: number;
  routes_covered: number;
  laspeyres?: number;
  paasche?: number;
  fisher?: number;
}

export interface BacktestReport {
  method: string;
  days_available: number;
  target_days: number;
  status: "mature" | "accumulating";
  note: string;
  dates?: string[];
  values?: number[];
  day_over_day_pct_changes?: number[];
  volatility_stdev_pct?: number | null;
  min_value?: number | null;
  max_value?: number | null;
}

export interface MospiCpiReference {
  series_base: string;
  reference_month: string;
  reference_month_label: string;
  published_date: string;
  next_release_date: string;
  headline_cpi_index: number;
  headline_cpi_yoy_pct: number;
  transport_division_index: number;
  transport_division_yoy_pct: number;
  passenger_transport_index: number;
  passenger_transport_yoy_pct: number;
  source_url: string;
  source_note: string;
}

export interface CpiDivergence {
  has_signal: boolean;
  alert: boolean;
  message: string;
  apix_change_pct: number | null;
  apix_days_tracked: number | null;
  apix_first_date: string | null;
  apix_last_date: string | null;
  ratio_vs_official_yoy: number | null;
  mospi: MospiCpiReference;
}

export interface ComplianceStatus {
  source_id: string;
  name: string;
  kind: string;
  domain: string;
  allowed: boolean | null;
  reason: string | null;
  checked_at: string | null;
}

export interface ElasticityPoint {
  ap_window_days: number;
  mean_fare: number;
  min_fare: number;
  max_fare: number;
  sample_size: number;
  elasticity_vs_prev?: number | null;
}

export interface BookingAdvice {
  has_signal: boolean;
  verdict: "book_early" | "can_wait" | "no_strong_pattern" | null;
  message: string;
  cheapest_window_days: number | null;
  cheapest_mean_fare: number | null;
  priciest_window_days: number | null;
  priciest_mean_fare: number | null;
  gap_pct: number | null;
  windows_with_data: number;
  confidence: "low" | "medium" | "high" | null;
}

export interface PriceHistoryPoint {
  search_date: string;
  cheapest_fare: number;
  mean_fare: number;
  sample_size: number;
}

export interface RoutePriceHistory {
  route: string;
  days_of_history: number;
  points: PriceHistoryPoint[];
  typical_low: number | null;
  typical_high: number | null;
  lowest_seen: number | null;
  highest_seen: number | null;
  latest_cheapest_fare: number | null;
  latest_search_date: string | null;
}

export interface HeatmapCell {
  route: string;
  ap_window_days: number;
  mean_fare: number;
  min_fare: number;
  sample_size: number;
}

export interface PriceGridCell {
  route: string;
  ap_window_days: number;
  mean_fare: number;
  sample_size: number;
  is_estimated: boolean;
  confidence: "high" | "medium" | "low" | null;
  basis: string | null;
  range_low: number | null;
  range_high: number | null;
}

export interface PriceGrid {
  cells: PriceGridCell[];
  reference_window_days: number | null;
  total_cells: number;
  real_cells: number;
  estimated_cells: number;
}

export interface DateWatchCheckpoint {
  ap_window_days: number;
  checkpoint_date: string;
  status: "collected" | "sold_out" | "missed" | "checking_today" | "upcoming";
  mean_fare: number | null;
  min_fare: number | null;
  sample_size: number;
  is_estimated: boolean;
  confidence: "high" | "medium" | "low" | null;
  basis: string | null;
  range_low: number | null;
  range_high: number | null;
}

export interface DateWatch {
  travel_date: string;
  checkpoints: DateWatchCheckpoint[];
  has_signal: boolean;
  message: string;
  cheapest_so_far: DateWatchCheckpoint | null;
  priciest_so_far: DateWatchCheckpoint | null;
  gap_pct: number | null;
}

export interface SpikeCalendarWindow {
  key: string;
  name: string;
  start: string;
  end: string;
  why: string;
  in_scraping_horizon: boolean;
}

export interface RouteSpikeSignal {
  route: string;
  window_key: string;
  window_name: string;
  spike_mean_fare: number;
  baseline_mean_fare: number;
  pct_change: number;
  spike_sample_size: number;
  baseline_sample_size: number;
}

export interface SpikeWatch {
  as_of: string;
  calendar: SpikeCalendarWindow[];
  route_signals: RouteSpikeSignal[];
}

export interface FestivalRoutePrice {
  route: string;
  price: number;
  is_estimated: boolean;
  sample_size: number;
  confidence: "high" | "medium" | "low" | null;
  basis: string | null;
  range_low: number | null;
  range_high: number | null;
  baseline_price: number | null;
  baseline_is_estimated: boolean;
  baseline_sample_size: number;
  pct_change: number | null;
}

export interface FestivalRoutePrices {
  window_key: string;
  window_name: string;
  start: string;
  end: string;
  why: string;
  routes: FestivalRoutePrice[];
}

export interface RouteAffordability {
  route: string;
  origin: string;
  destination: string;
  distance_km: number;
  mean_fare: number;
  cheapest_fare: number;
  sample_size: number;
  cost_per_km: number;
  wage_days_male_casual_labour: number;
  wage_days_female_casual_labour: number;
}

export interface WageReference {
  report_label: string;
  survey_period: string;
  published_date: string;
  casual_labour_daily_wage_male_inr: number;
  casual_labour_daily_wage_female_inr: number;
  regular_salaried_monthly_earnings_male_inr: number;
  regular_salaried_monthly_earnings_female_inr: number;
  self_employed_monthly_earnings_male_inr: number;
  self_employed_monthly_earnings_female_inr: number;
  source_url: string;
  source_note: string;
}

export interface AffordabilityReport {
  routes: RouteAffordability[];
  cheapest_per_km_route: string | null;
  most_expensive_per_km_route: string | null;
  cost_per_km_gap_pct: number | null;
  wage_reference: WageReference;
}

export interface CoverageReport {
  routes_in_basket: number;
  ap_windows: number[];
  total_cells: number;
  cells_with_data: number;
  coverage_pct: number;
  sources_contributing: string[];
  missing_cells: string[];
}

export interface FareQuote {
  id: number;
  route: string;
  carrier_code: string;
  source_id: string;
  ap_window_days: number;
  search_date: string;
  travel_date: string;
  fare_class: string;
  base_fare: number | null;
  taxes_fees: number | null;
  total_fare: number | null;
  is_outlier: boolean;
  sold_out: boolean;
}

export interface NewsItem {
  title: string;
  link: string;
  source: string;
  published_at: string | null;
  categories: string[];
  summary: string;
}

export interface NewsSourceCheck {
  name: string;
  allowed: boolean;
  reason: string;
}

export interface News {
  items: NewsItem[];
  as_of: string;
  sources_checked: NewsSourceCheck[];
}

export interface CarrierIndexPoint {
  date: string;
  laspeyres: number;
  paasche: number;
  fisher: number;
  sample_size: number;
  routes_covered: number;
}

export interface CarrierIndexSeries {
  carrier_code: string;
  carrier_name: string;
  carrier_weight: number;
  points: CarrierIndexPoint[];
}

export interface ByCarrierIndex {
  headline: IndexDailyPoint[];
  carriers: CarrierIndexSeries[];
}

export interface CarrierFinancialQuarter {
  quarter_label: string;
  period_start: string;
  period_end: string;
  revenue_cr: number;
  net_profit_cr: number;
  net_margin_pct: number;
  filing_date: string;
  source_url: string;
  source_note: string;
}

export interface InvestorRelationsCompliance {
  domain: string;
  path: string;
  allowed: boolean;
  reason: string;
}

export interface CarrierFinancialContext {
  carrier_code: string;
  carrier_name: string;
  available: boolean;
  reason: string | null;
  quarters: CarrierFinancialQuarter[];
  compliance: InvestorRelationsCompliance | null;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  routes: () => getJSON<RouteOut[]>("/routes"),
  compliance: () => getJSON<ComplianceStatus[]>("/compliance"),
  coverage: () => getJSON<CoverageReport>("/coverage"),
  indexDaily: () => getJSON<IndexDailyPoint[]>("/index/daily"),
  backtest: (method = "fisher") => getJSON<BacktestReport>(`/index/backtest?method=${method}`),
  cpiDivergence: () => getJSON<CpiDivergence>("/index/cpi-divergence"),
  elasticity: (routeId?: number | null) =>
    getJSON<ElasticityPoint[]>(routeId ? `/elasticity?route_id=${routeId}` : "/elasticity"),
  bookingAdvice: (routeId: number) => getJSON<BookingAdvice>(`/booking-advice?route_id=${routeId}`),
  priceHistory: (routeId: number) => getJSON<RoutePriceHistory>(`/price-history?route_id=${routeId}`),
  spikeWatch: () => getJSON<SpikeWatch>("/spike-watch"),
  festivalRoutePrices: (windowKey: string) => getJSON<FestivalRoutePrices>(`/spike-watch/${windowKey}/prices`),
  affordability: () => getJSON<AffordabilityReport>("/affordability"),
  dateWatch: (routeId: number, travelDate: string) =>
    getJSON<DateWatch>(`/date-watch?route_id=${routeId}&travel_date=${travelDate}`),
  heatmap: () => getJSON<HeatmapCell[]>("/heatmap"),
  priceGrid: () => getJSON<PriceGrid>("/price-grid"),
  fares: () => getJSON<FareQuote[]>("/fares?limit=300"),
  news: () => getJSON<News>("/news"),
  indexByCarrier: () => getJSON<ByCarrierIndex>("/index/by-carrier"),
  carriersFinancialContext: () => getJSON<CarrierFinancialContext[]>("/carriers/financial-context"),
};
