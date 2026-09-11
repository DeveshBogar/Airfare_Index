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

// Fixed-basket (Laspeyres) and updated-basket (Paasche) only diverge from
// the headline once the routes actually contributing prices shift between
// days - with this little real history, they usually haven't yet, so the
// tooltip would otherwise show the same number three times. Below this gap
// (in index points) the two secondary methods are folded into one "agrees
// with the headline" line instead of repeating an identical value.
const AGREEMENT_THRESHOLD = 0.05;

function TrendTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { payload?: IndexDailyPoint }[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload;
  if (!row || row.fisher == null) return null;

  const headline = row.fisher;
  const others = SERIES.filter((s) => s.key !== "fisher" && row[s.key as "laspeyres" | "paasche"] != null);
  const diverging = others.filter(
    (s) => Math.abs((row[s.key as "laspeyres" | "paasche"] as number) - headline) >= AGREEMENT_THRESHOLD
  );
  const agreeing = others.filter((s) => !diverging.includes(s));

  return (
    <div className="rounded-lg border border-border bg-surface-raised px-3 py-2 text-[13px] shadow-sm">
      <div className="font-semibold text-ink mb-1">Index — {label}</div>
      <div style={{ color: "var(--color-series-3)" }} className="font-medium">
        Balanced average (headline): {headline.toFixed(1)}
      </div>
      {diverging.map((s) => (
        <div key={s.key} style={{ color: s.color }}>
          {s.label}: {(row[s.key as "laspeyres" | "paasche"] as number).toFixed(1)}
        </div>
      ))}
      {agreeing.length > 0 && (
        <div className="text-ink-muted text-xs mt-1">
          {agreeing.map((s) => s.label).join(" and ")} {agreeing.length === 1 ? "agrees" : "agree"} with the headline
          here.
        </div>
      )}
    </div>
  );
}

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
            <Tooltip content={<TrendTooltip />} />
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
