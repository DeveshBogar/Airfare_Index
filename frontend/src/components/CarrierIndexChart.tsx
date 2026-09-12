import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ByCarrierIndex } from "../api";
import { Panel } from "./Panel";

const HEADLINE_COLOR = "var(--color-series-3)"; // same token TrendChart uses for "Balanced average (headline)"
const CARRIER_COLORS = [
  "var(--color-series-4)",
  "var(--color-series-5)",
  "var(--color-series-6)",
  "var(--color-series-7)",
  "var(--color-series-8)",
];

interface ChartRow {
  date: string;
  headline?: number;
  [carrierKey: string]: string | number | undefined;
}

interface CarrierTooltipPayloadItem {
  dataKey?: string;
  name?: string;
  value?: number;
  color?: string;
}

function CarrierIndexTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: CarrierTooltipPayloadItem[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  // Real gaps (a carrier with no observation that day) come through as
  // undefined values - shown as a gap in the line itself, and skipped
  // here rather than printed as "0" or hidden silently either way.
  const present = payload.filter((entry) => entry.value != null);
  if (present.length === 0) return null;
  return (
    <div className="rounded-lg border border-border bg-surface-raised px-3 py-2 text-[13px] shadow-sm">
      <div className="font-semibold text-ink mb-1">Index — {label}</div>
      {present.map((entry) => (
        <div key={entry.dataKey} style={{ color: entry.color }}>
          {entry.name}: {Number(entry.value).toFixed(1)}
        </div>
      ))}
    </div>
  );
}

export function CarrierIndexChart({ data }: { data: ByCarrierIndex | null }) {
  const carriers = data?.carriers ?? [];
  const headline = data?.headline ?? [];

  const rows = new Map<string, ChartRow>();
  for (const p of headline) {
    rows.set(p.date, { date: p.date, headline: p.fisher });
  }
  for (const carrier of carriers) {
    const key = `c_${carrier.carrier_code}`;
    for (const p of carrier.points) {
      const row = rows.get(p.date) ?? { date: p.date };
      row[key] = p.fisher;
      rows.set(p.date, row);
    }
  }
  const chartData = Array.from(rows.values()).sort((a, b) => a.date.localeCompare(b.date));
  const hasEnoughData = chartData.length >= 2 && carriers.length > 0;

  return (
    <Panel
      title="How each airline's fares have moved"
      subtitle={
        "Same Laspeyres/Paasche/Fisher construction as the headline index above, computed separately for each " +
        "airline's own fares — so you can see whether one carrier is driving a move the blended number shows, " +
        "or moving against it. Each carrier's legend weight is its real, DGCA-route-weighted share of the " +
        "prices this project has actually collected — not an official passenger market-share figure; see " +
        "docs/financial_context_methodology.md for exactly what it does and doesn't mean."
      }
    >
      {!hasEnoughData ? (
        <div className="h-[220px] flex flex-col items-center justify-center text-center text-sm text-ink-secondary gap-1">
          <div className="font-medium text-ink">Not enough real per-carrier history yet</div>
          <div>Needs at least 2 real days of data from more than one carrier — it grows every time prices are checked again.</div>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
            <CartesianGrid stroke="var(--color-hairline)" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 12, fill: "var(--color-ink-muted)" }} axisLine={{ stroke: "var(--color-axis)" }} tickLine={false} />
            <YAxis domain={["auto", "auto"]} tick={{ fontSize: 12, fill: "var(--color-ink-muted)" }} axisLine={false} tickLine={false} />
            <Tooltip content={<CarrierIndexTooltip />} />
            <Legend
              formatter={(_value, entry) => {
                if (entry.dataKey === "headline") {
                  return <span style={{ color: "var(--color-ink-secondary)", fontSize: 12 }}>Balanced average (headline)</span>;
                }
                const carrier = carriers.find((c) => `c_${c.carrier_code}` === entry.dataKey);
                const label = carrier ? `${carrier.carrier_name} (${Math.round(carrier.carrier_weight * 100)}%)` : String(entry.dataKey ?? "");
                return <span style={{ color: "var(--color-ink-secondary)", fontSize: 12 }}>{label}</span>;
              }}
            />
            <Line
              type="monotone"
              dataKey="headline"
              name="Balanced average (headline)"
              stroke={HEADLINE_COLOR}
              strokeWidth={2.5}
              dot={false}
            />
            {carriers.map((carrier, i) => (
              <Line
                key={carrier.carrier_code}
                type="monotone"
                dataKey={`c_${carrier.carrier_code}`}
                name={carrier.carrier_name}
                stroke={CARRIER_COLORS[i % CARRIER_COLORS.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
