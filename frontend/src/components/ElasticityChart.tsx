import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ElasticityPoint, RouteOut } from "../api";
import { AP_WINDOW_SHORT, apWindowFull, formatINR } from "../labels";
import { Panel } from "./Panel";

interface ElasticityTooltipItem {
  dataKey?: string;
  name?: string;
  value?: number;
  payload?: { full?: string };
}

// A custom tooltip, not Recharts' default formatter: the bar's own fill
// (color-mix(...15%...)) is deliberately pale so it reads as a quiet
// background band on the chart - but Recharts' default tooltip reuses
// that same series color for the tooltip text, which made "Highest price
// seen" nearly unreadable against the tooltip background. Each row here
// gets its own explicit, legible color instead of inheriting the chart's
// render color.
function ElasticityTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: ElasticityTooltipItem[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const full = payload[0]?.payload?.full ?? label;
  return (
    <div className="rounded-lg border border-border bg-surface-raised px-3 py-2 text-[13px] shadow-sm">
      <div className="font-semibold text-ink mb-1">{full}</div>
      {payload.map((entry) => (
        <div
          key={entry.dataKey}
          style={{ color: entry.dataKey === "mean_fare" ? "var(--color-series-1)" : "var(--color-ink-secondary)" }}
        >
          {entry.name}: {formatINR(Number(entry.value ?? 0))}
        </div>
      ))}
    </div>
  );
}

export function ElasticityChart({ data, routeFilter }: { data: ElasticityPoint[]; routeFilter: RouteOut | null }) {
  const chartData = data.map((d) => ({
    ...d,
    label: AP_WINDOW_SHORT[d.ap_window_days] ?? `${d.ap_window_days}d`,
    full: apWindowFull(d.ap_window_days),
  }));

  return (
    <Panel
      title="Book early, pay less"
      subtitle={
        routeFilter
          ? `Average cheapest price on ${routeFilter.display_name}, by how far ahead it was booked.`
          : "Average cheapest price across all tracked routes, by how far ahead it was booked."
      }
    >
      {chartData.length === 0 ? (
        <div className="h-[220px] flex items-center justify-center text-sm text-ink-secondary">
          No prices collected yet.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
            <CartesianGrid stroke="var(--color-hairline)" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: "var(--color-ink-muted)" }} axisLine={{ stroke: "var(--color-axis)" }} tickLine={false} />
            {/* Two Y axes on purpose: the bar (highest price seen) has to
                start at 0 to read honestly as a bar, but sharing that same
                0-based scale flattened the average-price line into a barely-
                moving smudge near the bottom - the real day-to-day swings in
                the average were only a few hundred rupees against a ~20,000
                axis. The line gets its own tightly-zoomed axis so its actual
                shape (the whole point of "book early, pay less") is visible,
                without changing a single underlying number. */}
            <YAxis
              yAxisId="bars"
              tick={{ fontSize: 12, fill: "var(--color-ink-muted)" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => formatINR(Number(v))}
              width={64}
            />
            <YAxis
              yAxisId="line"
              orientation="right"
              domain={["auto", "auto"]}
              tick={{ fontSize: 12, fill: "var(--color-series-1)" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => formatINR(Number(v))}
              width={64}
            />
            <Tooltip content={<ElasticityTooltip />} />
            <Bar
              yAxisId="bars"
              dataKey="max_fare"
              name="Highest price seen"
              fill="color-mix(in oklab, var(--color-series-1) 15%, transparent)"
              stroke="none"
              barSize={28}
            />
            <Line
              yAxisId="line"
              type="monotone"
              dataKey="mean_fare"
              name="Average cheapest price"
              stroke="var(--color-series-1)"
              strokeWidth={2.5}
              dot={{ r: 4, fill: "var(--color-series-1)" }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
