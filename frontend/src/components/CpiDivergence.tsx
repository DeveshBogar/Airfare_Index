import type { CpiDivergence as CpiDivergenceData } from "../api";
import { Panel } from "./Panel";

function Bar({ label, valuePct, maxPct, tone }: { label: string; valuePct: number; maxPct: number; tone: "muted" | "primary" }) {
  const widthPct = maxPct > 0 ? Math.max((valuePct / maxPct) * 100, 2) : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-sm mb-1">
        <span className="text-ink-secondary">{label}</span>
        <span className="font-semibold text-ink tabular-nums">{valuePct.toFixed(valuePct < 10 ? 1 : 0)}%</span>
      </div>
      <div className="h-3 rounded-full bg-page overflow-hidden">
        <div
          className={"h-full rounded-full " + (tone === "primary" ? "bg-series-1" : "bg-ink-muted")}
          style={{ width: `${widthPct}%` }}
        />
      </div>
    </div>
  );
}

export function CpiDivergence({ data }: { data: CpiDivergenceData }) {
  if (!data.has_signal) {
    return (
      <Panel title="Is official inflation data keeping up with real airfares?">
        <p className="text-sm text-ink-secondary">{data.message}</p>
      </Panel>
    );
  }

  const apixAbs = Math.abs(data.apix_change_pct ?? 0);
  const officialAbs = Math.abs(data.mospi.passenger_transport_yoy_pct);
  const maxScale = Math.max(apixAbs, officialAbs);

  return (
    <Panel
      title="Is official inflation data keeping up with real airfares?"
      subtitle="Official CPI is published once a month and only captures a single snapshot. We check real fares every day — this compares how much each has actually moved."
    >
      {data.alert && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-warning/15 text-ink text-sm font-medium px-3 py-2">
          <span className="h-1.5 w-1.5 rounded-full bg-warning shrink-0" aria-hidden />
          Real fares have already moved more than official CPI captured in a full year
        </div>
      )}

      {data.ratio_vs_official_yoy != null && (
        <div className="mb-4">
          <span className="text-[40px] leading-none font-semibold text-ink">{data.ratio_vs_official_yoy.toFixed(1)}×</span>
          <span className="text-sm text-ink-secondary ml-2">
            as much movement in {data.apix_days_tracked} real day{data.apix_days_tracked === 1 ? "" : "s"} as official CPI
            recorded in a whole year
          </span>
        </div>
      )}

      <div className="flex flex-col gap-3 max-w-xl">
        <Bar
          label={`Official CPI — Passenger transport services (full year to ${data.mospi.reference_month_label})`}
          valuePct={officialAbs}
          maxPct={maxScale}
          tone="muted"
        />
        <Bar
          label={`APIx — real tracked movement (last ${data.apix_days_tracked} real day${data.apix_days_tracked === 1 ? "" : "s"})`}
          valuePct={apixAbs}
          maxPct={maxScale}
          tone="primary"
        />
      </div>

      <p className="text-sm text-ink-secondary mt-4 leading-relaxed max-w-2xl">{data.message}</p>

      <details className="mt-3 text-xs text-ink-muted">
        <summary className="cursor-pointer">Where this official figure comes from</summary>
        <p className="mt-1.5 leading-relaxed max-w-2xl">
          {data.mospi.source_note} Published {data.mospi.published_date} by the National Statistics Office
          (MoSPI), base {data.mospi.series_base}. For context, the broader "Transport" division moved{" "}
          {data.mospi.transport_division_yoy_pct.toFixed(2)}% and headline CPI moved{" "}
          {data.mospi.headline_cpi_yoy_pct.toFixed(2)}% over the same year.{" "}
          <a href={data.mospi.source_url} target="_blank" rel="noreferrer" className="underline hover:text-ink-secondary">
            Source (MoSPI press release, PDF)
          </a>
          . Next official release: {data.mospi.next_release_date}.
        </p>
      </details>
    </Panel>
  );
}
