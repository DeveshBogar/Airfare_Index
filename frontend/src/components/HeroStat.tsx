import type { BacktestReport, IndexDailyPoint } from "../api";

function takeawaySentence(change: number | null, days: number): string {
  if (days <= 1) return "We've only just started tracking — check back tomorrow for the first day-over-day move.";
  if (change == null) return "Not enough data yet to describe a trend.";
  const abs = Math.abs(change);
  if (abs < 0.5) return "Prices are holding roughly steady across tracked routes since yesterday.";
  const direction = change > 0 ? "risen" : "fallen";
  return `Prices have ${direction} about ${abs.toFixed(1)}% across tracked routes since yesterday.`;
}

export function HeroStat({ daily, backtest }: { daily: IndexDailyPoint[]; backtest: BacktestReport }) {
  const latest = daily.at(-1);
  const prev = daily.length > 1 ? daily.at(-2) : undefined;
  const change =
    latest?.fisher != null && prev?.fisher != null ? ((latest.fisher - prev.fisher) / prev.fisher) * 100 : null;
  const up = change != null && change > 0.05;
  const down = change != null && change < -0.05;

  return (
    <section className="card-shadow rounded-2xl border border-border bg-surface p-6 flex flex-col sm:flex-row sm:items-end justify-between gap-5">
      <div>
        <div className="text-sm font-medium text-ink-secondary">Today's airfare price index</div>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mt-1">
          <span className="text-[48px] leading-none font-semibold text-ink figures-tabular">
            {latest?.fisher != null ? latest.fisher.toFixed(1) : "—"}
          </span>
          {change != null && (
            <span
              // A rising index means pricier flights — bad news for travellers —
              // so "up" reads as the unfavourable colour here, not success green.
              className={
                "text-base font-medium whitespace-nowrap " +
                (up ? "text-critical" : down ? "text-success-text" : "text-ink-muted")
              }
            >
              {up ? "▲" : down ? "▼" : "▬"} {Math.abs(change).toFixed(1)}% vs. yesterday
            </span>
          )}
        </div>
        <p className="text-sm text-ink-secondary mt-2 max-w-xl leading-relaxed">
          {takeawaySentence(change, backtest.days_available)}
        </p>
      </div>
      <div className="text-xs text-ink-muted sm:text-right leading-relaxed shrink-0">
        <div>100 = prices on the day we started tracking</div>
        <div>{latest ? `Last updated ${latest.date}` : "No data yet"}</div>
      </div>
    </section>
  );
}
