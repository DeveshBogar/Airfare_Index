import type { BacktestReport, CoverageReport } from "../api";

function plainHistorySentence(backtest: BacktestReport): string {
  if (backtest.days_available === 0) return "We haven't collected any history yet.";
  if (backtest.status === "mature") {
    return `We now have a full ${backtest.target_days}-day price history to compare against.`;
  }
  return `We have ${backtest.days_available} of ${backtest.target_days} days of real history so far — there's no independent published series of Indian airfares to check against, so we're building our own track record day by day instead of estimating one.`;
}

export function Footer({ backtest, coverage }: { backtest: BacktestReport; coverage: CoverageReport }) {
  return (
    <div className="text-xs text-ink-muted pb-6 leading-relaxed">
      <p className="mb-1">{plainHistorySentence(backtest)}</p>
      {backtest.note && (
        <details className="mb-1">
          <summary className="cursor-pointer text-ink-secondary">Technical note</summary>
          <p className="mt-1 leading-relaxed">{backtest.note}</p>
        </details>
      )}
      {coverage.missing_cells.length > 0 && (
        <details>
          <summary className="cursor-pointer text-ink-secondary">
            {coverage.missing_cells.length} route/booking-window combination
            {coverage.missing_cells.length === 1 ? "" : "s"} with no price yet — click to list
          </summary>
          <p className="mt-1 leading-relaxed">{coverage.missing_cells.join(" · ")}</p>
        </details>
      )}
    </div>
  );
}
