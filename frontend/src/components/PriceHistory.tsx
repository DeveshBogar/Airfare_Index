import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { RoutePriceHistory, RouteOut } from "../api";
import { formatINR } from "../labels";
import { Panel } from "./Panel";

function formatShortDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

function PriceHistoryChart({ data }: { data: RoutePriceHistory }) {
  const chartData = data.points.map((p) => ({ ...p, label: formatShortDate(p.search_date) }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
        <CartesianGrid stroke="var(--color-hairline)" vertical={false} />
        <XAxis dataKey="label" tick={{ fontSize: 12, fill: "var(--color-ink-muted)" }} axisLine={{ stroke: "var(--color-axis)" }} tickLine={false} />
        <YAxis
          domain={["auto", "auto"]}
          tick={{ fontSize: 12, fill: "var(--color-ink-muted)" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => formatINR(Number(v))}
          width={64}
        />
        <Tooltip
          contentStyle={{
            background: "var(--color-surface-raised)",
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            fontSize: 13,
          }}
          formatter={(value, name, entry) => {
            if (name !== "cheapest_fare") return [formatINR(Number(value)), name];
            const n = entry.payload?.sample_size ?? 0;
            return [`${formatINR(Number(value))} (cheapest of ${n} price${n === 1 ? "" : "s"} found that day)`, "Cheapest fare"];
          }}
          labelFormatter={(label) => `Checked on ${label}`}
        />
        <Line
          type="monotone"
          dataKey="cheapest_fare"
          stroke="var(--color-series-1)"
          strokeWidth={2.5}
          dot={{ r: 4, fill: "var(--color-series-1)" }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function RangeBar({ data }: { data: RoutePriceHistory }) {
  const { lowest_seen, highest_seen, latest_cheapest_fare, typical_low, typical_high } = data;
  if (lowest_seen == null || highest_seen == null || latest_cheapest_fare == null) return null;

  const span = highest_seen - lowest_seen;
  // A genuinely zero spread (every real day found the exact same cheapest
  // fare) has no "range" to visualize honestly - a cold-to-warm gradient
  // would imply variation that was never actually observed, so this case
  // renders a plain neutral bar with a single centered marker instead.
  if (span <= 0) {
    return (
      <div className="mt-3">
        <div className="relative h-2 rounded-full overflow-hidden" style={{ background: "var(--color-diverge-mid)" }}>
          <div className="absolute inset-y-0 left-1/2 w-3 -ml-1.5 rounded-full bg-series-1" />
        </div>
        <div className="text-xs text-ink-muted mt-1 text-center">{formatINR(latest_cheapest_fare)} every time</div>
      </div>
    );
  }

  const pos = ((latest_cheapest_fare - lowest_seen) / span) * 100;
  const typicalLowPos = typical_low != null ? ((typical_low - lowest_seen) / span) * 100 : 0;
  const typicalHighPos = typical_high != null ? ((typical_high - lowest_seen) / span) * 100 : 100;

  return (
    <div className="mt-3">
      <div className="relative h-2 rounded-full overflow-hidden" style={{ background: "var(--color-diverge-mid)" }}>
        <div
          className="absolute inset-y-0"
          style={{
            left: `${typicalLowPos}%`,
            right: `${100 - typicalHighPos}%`,
            background:
              "linear-gradient(to right, color-mix(in oklab, var(--color-diverge-cold) 55%, var(--color-surface)), color-mix(in oklab, var(--color-diverge-warm) 55%, var(--color-surface)))",
          }}
        />
      </div>
      <div
        className="relative h-3 w-3 -mt-2.5 rounded-full border-2 border-surface bg-series-1 shadow"
        style={{ marginLeft: `calc(${pos}% - 6px)` }}
        title={`Most recent cheapest fare: ${formatINR(latest_cheapest_fare)}`}
      />
      <div className="flex justify-between text-xs text-ink-muted mt-1">
        <span>{formatINR(lowest_seen)}</span>
        <span>{formatINR(highest_seen)}</span>
      </div>
    </div>
  );
}

function positionMessage(data: RoutePriceHistory): string {
  const { latest_cheapest_fare, typical_low, typical_high, days_of_history } = data;
  if (latest_cheapest_fare == null || typical_low == null || typical_high == null) return "";
  if (typical_low === typical_high) {
    // Collapsed range has two real, distinct causes - a single data point
    // (nothing to compare yet) vs. several real days that all happened to
    // find the exact same cheapest fare (real price stability) - conflating
    // them would misreport genuine multi-day stability as "no data yet".
    return days_of_history <= 1
      ? "the only real price we've found for this route so far"
      : "the same as every real cheapest price we've found for this route so far";
  }
  if (latest_cheapest_fare <= typical_low) return "cheaper than usual right now";
  if (latest_cheapest_fare >= typical_high) return "pricier than usual right now";
  return "typical for this route right now";
}

export function PriceHistory({
  data,
  route,
  loading,
}: {
  data: RoutePriceHistory | null;
  route: RouteOut | null;
  loading: boolean;
}) {
  if (!route) {
    return (
      <Panel title="Price history">
        <p className="text-sm text-ink-secondary">Pick a route above to see how its real prices have moved over the days we've checked it.</p>
      </Panel>
    );
  }

  return (
    <Panel
      title="Price history"
      subtitle={`Real cheapest price found for ${route.display_name} each day we've checked it — grows by one real day every day we run, nothing estimated or backfilled.`}
    >
      {loading || !data ? (
        <div className="h-16 flex items-center text-sm text-ink-muted">Checking real prices for this route…</div>
      ) : data.days_of_history === 0 ? (
        <p className="text-sm text-ink-secondary">We haven't collected any real prices for this route yet.</p>
      ) : (
        <div className="flex flex-col gap-4">
          <div>
            <div className="text-2xl font-semibold text-ink figures-tabular">
              {formatINR(data.latest_cheapest_fare ?? 0)}{" "}
              <span className="text-sm font-normal text-ink-secondary">is {positionMessage(data)}</span>
            </div>
            {data.days_of_history > 1 && data.typical_low != null && data.typical_high != null && (
              <p className="text-sm text-ink-secondary mt-1">
                The cheapest real price we've found for this route usually falls between {formatINR(data.typical_low)}–
                {formatINR(data.typical_high)}.
              </p>
            )}
            <RangeBar data={data} />
          </div>

          {data.days_of_history >= 2 ? (
            <div>
              <div className="text-sm font-medium text-ink mb-1">How it's moved</div>
              <PriceHistoryChart data={data} />
            </div>
          ) : (
            <p className="text-xs text-ink-muted">
              Only 1 real day of history so far — a trend line needs at least 2. It grows every time we check this route
              again.
            </p>
          )}

          <p className="text-xs text-ink-muted">
            Based on {data.days_of_history} real day{data.days_of_history === 1 ? "" : "s"} of scraping so far — real
            prices only, never filled in or guessed.
          </p>
        </div>
      )}
    </Panel>
  );
}
