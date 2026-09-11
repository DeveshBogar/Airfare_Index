import type { IndexDailyPoint } from "../api";

interface TrendSummary {
  direction: "up" | "down" | "flat";
  headline: string;
  recommendation: string;
}

// A page-level, always-visible takeaway so a reader (sighted or on a screen
// reader) gets the whole story from one sentence, without having to read the
// trend chart or do the arithmetic themselves. Built only from real fisher
// (headline) index values already computed by the backend — never invents a
// number.
//
// Scrapes don't run every single calendar day (a route/window can be
// skipped, gated, or fail), so "7 days" must mean 7 real samples, not a
// calendar cutoff — counting by date would silently claim continuity across
// gaps the rest of the app is careful to disclose (see the "N of 30 real
// days" tracker). When fewer than 8 real samples exist at all, this says so
// plainly instead of implying a full week has passed.
function summarizeTrend(daily: IndexDailyPoint[]): TrendSummary | null {
  const points = daily.filter((d): d is IndexDailyPoint & { fisher: number } => d.fisher != null);
  if (points.length < 2) return null;

  const windowSize = Math.min(points.length, 7);
  const windowPoints = points.slice(-windowSize);
  const start = windowPoints[0];
  const latest = windowPoints[windowPoints.length - 1];
  const usingFullHistory = points.length <= 7;

  const change = ((latest.fisher - start.fisher) / start.fisher) * 100;
  const direction: TrendSummary["direction"] = change > 0.5 ? "up" : change < -0.5 ? "down" : "flat";

  const arrow = direction === "up" ? "▲" : direction === "down" ? "▼" : "▬";
  const verb = direction === "up" ? "rose" : direction === "down" ? "fell" : "held roughly steady";
  const pct = `${change >= 0 ? "+" : ""}${change.toFixed(1)}%`;
  const span = usingFullHistory
    ? `the ${windowSize} real day${windowSize === 1 ? "" : "s"} we've tracked so far`
    : `the last ${windowSize} real days`;

  const headline =
    direction === "flat"
      ? `${arrow} Index ${verb} — ${start.fisher.toFixed(0)} to ${latest.fisher.toFixed(0)} over ${span} (${pct}).`
      : `${arrow} Index ${verb} from ${start.fisher.toFixed(0)} to ${latest.fisher.toFixed(0)} over ${span} (${pct}).`;

  const recommendation =
    direction === "up"
      ? "Prices have been climbing — if you need to fly soon, booking sooner rather than later is the safer bet."
      : direction === "down"
        ? "Prices have been easing — if your dates are flexible, it may be worth waiting a little before booking."
        : "Timing hasn't made much difference lately — no strong reason to rush or hold off.";

  return { direction, headline, recommendation };
}

export function PageSummary({ daily }: { daily: IndexDailyPoint[] }) {
  const summary = summarizeTrend(daily);

  return (
    <section
      aria-label="Quick summary of current airfare trends"
      className="card-shadow rounded-2xl border border-border bg-surface px-5 py-4"
    >
      {summary ? (
        <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-3">
          <p
            aria-live="polite"
            className={
              "text-[15px] font-semibold leading-relaxed shrink-0 " +
              (summary.direction === "up"
                ? "text-critical"
                : summary.direction === "down"
                  ? "text-success-text"
                  : "text-ink")
            }
          >
            {summary.headline}
          </p>
          <p className="text-sm text-ink-secondary leading-relaxed">{summary.recommendation}</p>
        </div>
      ) : (
        <p className="text-sm text-ink-secondary leading-relaxed">
          We've only just started tracking — a reliable trend summary will appear once a few more real days of
          prices have been collected.
        </p>
      )}
    </section>
  );
}
