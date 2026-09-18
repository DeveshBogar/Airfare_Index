import { getToken, type AuthUser } from "./auth";

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

export interface RegulatorFlag {
  id: number;
  route: string;
  route_id: number;
  carrier_code: string;
  carrier_name: string;
  ap_window_days: number;
  flagged_search_date: string;
  flagged_travel_date: string;
  observed_fare: number;
  baseline_median_fare: number;
  baseline_mad: number;
  robust_z_score: number;
  pct_above_baseline_median: number;
  baseline_sample_size: number;
  status: "new" | "reviewed" | "dismissed";
  review_note: string;
  reviewed_by: string;
  reviewed_at: string | null;
  detected_at: string;
  operator_response: string;
  operator_responded_by: string;
  operator_responded_at: string | null;
}

// Heterogeneous by design — each factor carries its own type's real fields.
export type PossibleFactor = { factor_type: string } & Record<string, unknown>;

export interface RegulatorFlagDetail extends RegulatorFlag {
  possible_factors: PossibleFactor[];
}

export interface DraftNotice {
  document_type: string;
  draft_disclaimer: string;
  flag_id: number;
  subject: Record<string, string | number>;
  observation: Record<string, number | string | null>;
  detection_method_note: string;
  possible_factors: PossibleFactor[];
  regulator_review: Record<string, string | null>;
  boundary_notice: string;
}

export interface CitizenFareReport {
  id: number;
  origin: string;
  destination: string;
  travel_date: string;
  reported_fare: number;
  carrier_name: string;
  note: string;
  contact_email: string;
  submitted_at: string;
  status: string;
  reviewer_note: string;
  reviewed_at: string | null;
}

export interface CitizenFareReportInput {
  origin: string;
  destination: string;
  travel_date: string;
  reported_fare: number;
  carrier_name?: string;
  note?: string;
  contact_email?: string;
}

export interface CitizenReportCount {
  total: number;
  new: number;
  reviewed: number;
}

export interface OperatorOverview {
  carrier_code: string;
  carrier_name: string;
  index: CarrierIndexSeries | null;
  headline: IndexDailyPoint[];
  latest_index_value: number | null;
  latest_index_date: string | null;
  quotes_collected: number;
  routes_covered: number;
  flags_total: number;
  flags_new: number;
  flags_awaiting_response: number;
}

export interface Session {
  token: string;
  expires_at: string;
  user: AuthUser;
}

/** Thrown when a call is refused for who you are (or aren't), so the UI can
 *  tell "your session ended, sign in again" (401) apart from "you're signed
 *  in, but this isn't yours" (403). Those need very different messages. */
export class AuthError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "AuthError";
    this.status = status;
  }
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Public reads. The token is attached when there is one — these endpoints
 *  do not require it, but a couple behave slightly differently for a known
 *  caller (a fare report gets attributed to the account that filed it). */
async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

async function authedFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...authHeaders(),
      ...(init.headers ?? {}),
    },
  });
  if (res.status === 401 || res.status === 403) {
    const detail = await res
      .json()
      .then((b) => (b as { detail?: string }).detail ?? "")
      .catch(() => "");
    throw new AuthError(res.status, detail || `HTTP ${res.status}`);
  }
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => (b as { detail?: string }).detail ?? "")
      .catch(() => "");
    throw new Error(detail || `${path} -> HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
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

  // Regulator surface — all of it requires the government role except
  // submitting a fare report and the aggregate report count, which are the
  // two things the public "Report a Fare" tab needs.
  regulatorFlags: (statusFilter?: string) =>
    authedFetch<RegulatorFlag[]>(
      statusFilter ? `/regulator/flags?status_filter=${encodeURIComponent(statusFilter)}` : "/regulator/flags",
    ),
  regulatorFlag: (id: number) => authedFetch<RegulatorFlagDetail>(`/regulator/flags/${id}`),
  // No reviewed_by: the server stamps the signed-in account, so the UI
  // cannot attribute a decision to anyone else.
  reviewFlag: (id: number, body: { status: string; review_note: string }) =>
    authedFetch<RegulatorFlag>(`/regulator/flags/${id}/review`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  draftNotice: (id: number) => authedFetch<DraftNotice>(`/regulator/flags/${id}/draft-notice`),
  citizenReportCount: () => getJSON<CitizenReportCount>("/regulator/citizen-reports/count"),
  // Needs an account — reading is open, writing is not. See
  // app/routers/regulator.py for why the write side is gated.
  submitCitizenReport: (body: CitizenFareReportInput) =>
    authedFetch<CitizenFareReport>("/regulator/citizen-reports", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  citizenReports: () => authedFetch<CitizenFareReport[]>("/regulator/citizen-reports"),
  reviewCitizenReport: (id: number, body: { status: string; reviewer_note: string }) =>
    authedFetch<CitizenFareReport>(`/regulator/citizen-reports/${id}/review`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  // Sign-in. The role lives on the account, so there is one login for all
  // three audiences rather than a per-role form.
  login: (username: string, password: string) =>
    authedFetch<Session>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => authedFetch<AuthUser>("/auth/me"),

  // Airline surface — every one of these is scoped server-side to the
  // signed-in operator's own carrier; there is no carrier parameter to pass.
  operatorOverview: () => authedFetch<OperatorOverview>("/operator/overview"),
  operatorFlags: () => authedFetch<RegulatorFlag[]>("/operator/flags"),
  operatorFares: () => authedFetch<FareQuote[]>("/operator/fares?limit=200"),
  respondToFlag: (id: number, response: string) =>
    authedFetch<RegulatorFlag>(`/operator/flags/${id}/response`, {
      method: "POST",
      body: JSON.stringify({ response }),
    }),

  myReports: () => authedFetch<CitizenFareReport[]>("/citizen/my-reports"),
};
