import type { BacktestReport, CoverageReport } from "../api";

function ProgressBar({ pct }: { pct: number }) {
  const clamped = Math.max(0, Math.min(100, pct));
  return (
    <div className="h-1.5 rounded-full bg-page overflow-hidden mt-2.5" role="presentation">
      <div className="h-full rounded-full bg-series-1" style={{ width: `${clamped}%` }} />
    </div>
  );
}

function Card({ label, value, sub, progressPct }: { label: string; value: string; sub?: string; progressPct?: number }) {
  return (
    <div className="card-shadow rounded-2xl border border-border bg-surface p-4">
      <div className="text-sm text-ink-secondary">{label}</div>
      <div className="text-2xl font-semibold mt-1 text-ink figures-tabular">{value}</div>
      {progressPct != null && <ProgressBar pct={progressPct} />}
      {sub && <div className="text-xs text-ink-muted mt-1.5 leading-relaxed">{sub}</div>}
    </div>
  );
}

export function KpiCards({ backtest, coverage }: { backtest: BacktestReport; coverage: CoverageReport }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,360px))] gap-3">
      <Card
        label="Days of history"
        value={`${backtest.days_available} of ${backtest.target_days}`}
        progressPct={(backtest.days_available / backtest.target_days) * 100}
        sub={
          backtest.status === "mature"
            ? "Full 30-day history reached"
            : "Builds by one real day every day we run — no filler data"
        }
      />
      <Card
        label="How complete is today's picture"
        value={`${coverage.coverage_pct}%`}
        progressPct={coverage.coverage_pct}
        sub={`${coverage.cells_with_data} of ${coverage.total_cells} route/booking-window checks have a real price`}
      />
      <Card
        label="Routes tracked"
        value={String(coverage.routes_in_basket)}
        sub={
          coverage.sources_contributing.length > 0
            ? `Live prices from: ${coverage.sources_contributing.join(", ")}`
            : "No live source has reported prices yet"
        }
      />
    </div>
  );
}
