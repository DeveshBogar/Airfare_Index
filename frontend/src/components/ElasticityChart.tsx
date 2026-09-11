import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ElasticityPoint, RouteOut } from "../api";
import { AP_WINDOW_SHORT, apWindowFull, formatINR } from "../labels";
import { Panel } from "./Panel";

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
            <YAxis tick={{ fontSize: 12, fill: "var(--color-ink-muted)" }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{
                background: "var(--color-surface-raised)",
                border: "1px solid var(--color-border)",
                borderRadius: 8,
                fontSize: 13,
              }}
              formatter={(v, name) => [formatINR(Number(v)), name]}
              labelFormatter={(_label, payload) => payload?.[0]?.payload?.full ?? _label}
            />
            <Bar
              dataKey="max_fare"
              name="Highest price seen"
              fill="color-mix(in oklab, var(--color-series-1) 15%, transparent)"
              stroke="none"
              barSize={28}
            />
            <Line
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
