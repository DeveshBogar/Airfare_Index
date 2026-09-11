import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { IndexDailyPoint } from "../api";
import { Panel } from "./Panel";

const SERIES = [
  { key: "laspeyres", label: "Fixed-basket method", color: "var(--color-series-1)" },
  { key: "paasche", label: "Updated-basket method", color: "var(--color-series-2)" },
  { key: "fisher", label: "Balanced average (headline)", color: "var(--color-series-3)" },
];

export function TrendChart({ data }: { data: IndexDailyPoint[] }) {
  return (
    <Panel
      title="How prices have moved"
      subtitle="100 = the day we started tracking. All three lines measure the same thing slightly differently and usually move together — the balanced average is the headline number above."
    >
      {data.length < 2 ? (
        <EmptyState days={data.length} />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
            <CartesianGrid stroke="var(--color-hairline)" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 12, fill: "var(--color-ink-muted)" }} axisLine={{ stroke: "var(--color-axis)" }} tickLine={false} />
            <YAxis domain={["auto", "auto"]} tick={{ fontSize: 12, fill: "var(--color-ink-muted)" }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{
                background: "var(--color-surface-raised)",
                border: "1px solid var(--color-border)",
                borderRadius: 8,
                fontSize: 13,
              }}
              labelFormatter={(label) => `Index — ${label}`}
              formatter={(value, name) => [Number(value).toFixed(1), name]}
            />
            <Legend
              formatter={(_value, entry) => {
                const s = SERIES.find((s) => s.key === entry.dataKey);
                return <span style={{ color: "var(--color-ink-secondary)", fontSize: 12 }}>{s?.label}</span>;
              }}
            />
            {SERIES.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                dot={false}
                strokeWidth={s.key === "fisher" ? 2.5 : 2}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}

function EmptyState({ days }: { days: number }) {
  return (
    <div className="h-[220px] flex flex-col items-center justify-center text-center text-sm text-ink-secondary gap-1">
      <div className="font-medium text-ink">
        {days} real day{days === 1 ? "" : "s"} of history so far
      </div>
      <div>A trend line needs at least 2 days — it grows every time prices are checked again.</div>
    </div>
  );
}
