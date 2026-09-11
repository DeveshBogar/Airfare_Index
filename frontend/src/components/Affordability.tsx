import type { AffordabilityReport, RouteAffordability } from "../api";
import { bookingLinkFor } from "../bookingLink";
import { formatINR } from "../labels";
import { Panel } from "./Panel";
import { PriceLink } from "./PriceLink";

function CostPerKmBar({ value, max }: { value: number; max: number }) {
  const widthPct = max > 0 ? Math.max((value / max) * 100, 3) : 0;
  return (
    <div className="h-2 rounded-full bg-page overflow-hidden w-full min-w-[60px]">
      <div className="h-full rounded-full bg-series-1" style={{ width: `${widthPct}%` }} />
    </div>
  );
}

function RouteRow({ row, maxCostPerKm }: { row: RouteAffordability; maxCostPerKm: number }) {
  // No single travel date underlies a route-level "typical fare" (it's
  // pooled across whatever real data exists), so the link leaves dates
  // open rather than implying one specific day.
  const link = bookingLinkFor({ origin: row.origin, destination: row.destination });
  return (
    <tr className="border-t border-hairline">
      <td className="py-2.5 pr-3 font-medium text-ink whitespace-nowrap">{row.route}</td>
      <td className="py-2.5 pr-3 text-ink-secondary whitespace-nowrap tabular-nums">{row.distance_km.toLocaleString("en-IN")} km</td>
      <td className="py-2.5 pr-3 text-ink-secondary whitespace-nowrap tabular-nums">
        <PriceLink href={link.url} label={link.label}>
          <span title={`Cheapest of ${row.sample_size} real price${row.sample_size === 1 ? "" : "s"} found for this route`}>
            {formatINR(row.cheapest_fare)}
          </span>
        </PriceLink>
      </td>
      <td className="py-2.5 pr-3">
        <div className="flex items-center gap-2 min-w-[140px]" title={`Based on the average of ${row.sample_size} real price(s): ${formatINR(row.mean_fare)}`}>
          <CostPerKmBar value={row.cost_per_km} max={maxCostPerKm} />
          <span className="text-ink font-medium tabular-nums whitespace-nowrap">₹{row.cost_per_km.toFixed(1)}/km</span>
        </div>
      </td>
      <td className="py-2.5 text-right text-ink font-medium tabular-nums whitespace-nowrap">
        {row.wage_days_male_casual_labour.toFixed(1)} days
      </td>
    </tr>
  );
}

export function Affordability({ data }: { data: AffordabilityReport }) {
  const { routes, cheapest_per_km_route, most_expensive_per_km_route, cost_per_km_gap_pct, wage_reference } = data;

  if (routes.length === 0) {
    return (
      <Panel title="What does this fare actually cost you?">
        <p className="text-sm text-ink-secondary">No route has enough real data yet to compute this.</p>
      </Panel>
    );
  }

  const maxCostPerKm = Math.max(...routes.map((r) => r.cost_per_km));

  return (
    <Panel
      title="What does this fare actually cost you?"
      subtitle="A price index number is abstract. Real distance and real wages make it concrete — here's every tracked route normalized against both."
    >
      {cheapest_per_km_route && most_expensive_per_km_route && cost_per_km_gap_pct != null && (
        <div className="mb-4 rounded-xl bg-page p-4">
          <p className="text-[15px] text-ink leading-relaxed">
            <strong>{most_expensive_per_km_route}</strong> costs{" "}
            <span className="font-semibold text-series-1">{cost_per_km_gap_pct.toFixed(0)}% more per km</span> to fly
            right now than <strong>{cheapest_per_km_route}</strong> — the same "per kilometre" idea used to compare
            train or bus fares, applied to flights.
          </p>
        </div>
      )}

      <p className="text-xs text-ink-muted mb-2">
        Click a "Cheapest fare" price to check current results for this route. Cost per km and days-of-wages use the
        average across all real fares (fare classes included), which is why it can look higher than the cheapest fare.
      </p>
      <div className="scroll-fade-x overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-ink-secondary">
              <th className="pb-2 pr-3 font-medium">Route</th>
              <th className="pb-2 pr-3 font-medium">Distance</th>
              <th className="pb-2 pr-3 font-medium">Cheapest fare</th>
              <th className="pb-2 pr-3 font-medium">
                Cost per km<span className="block text-xs font-normal text-ink-muted">average of all real fares</span>
              </th>
              <th className="pb-2 font-medium text-right">
                Days of wages<span className="block text-xs font-normal text-ink-muted">casual labour, male</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {routes.map((row) => (
              <RouteRow key={row.route} row={row} maxCostPerKm={maxCostPerKm} />
            ))}
          </tbody>
        </table>
      </div>

      <details className="mt-4 text-xs text-ink-muted">
        <summary className="cursor-pointer">Where the wage figures come from</summary>
        <div className="mt-1.5 leading-relaxed max-w-2xl space-y-1">
          <p>{wage_reference.source_note}</p>
          <p>
            Real, official figures — {wage_reference.report_label} ({wage_reference.survey_period}, published{" "}
            {wage_reference.published_date}): a casual labourer earns {formatINR(wage_reference.casual_labour_daily_wage_male_inr)}
            /day (male) or {formatINR(wage_reference.casual_labour_daily_wage_female_inr)}/day (female). For context, a
            regular salaried worker earns {formatINR(wage_reference.regular_salaried_monthly_earnings_male_inr)}/month
            (male) or {formatINR(wage_reference.regular_salaried_monthly_earnings_female_inr)}/month (female) — shown
            here as a monthly figure, not converted into a day-count.
          </p>
          <p>
            Distance is real great-circle distance between airports, not the actual flown distance (which is
            typically a little longer due to flight paths and routing).{" "}
            <a href={wage_reference.source_url} target="_blank" rel="noreferrer" className="underline hover:text-ink-secondary">
              Source (PLFS Annual Report 2025, PDF)
            </a>
            .
          </p>
        </div>
      </details>
    </Panel>
  );
}
