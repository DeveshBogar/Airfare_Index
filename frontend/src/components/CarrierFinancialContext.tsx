import type { CarrierFinancialContext as CarrierFinancialContextData, CarrierFinancialQuarter } from "../api";
import { Panel } from "./Panel";

function formatCrore(value: number): string {
  const sign = value < 0 ? "-" : "";
  return `${sign}₹${Math.abs(value).toLocaleString("en-IN", { maximumFractionDigits: 1 })} cr`;
}

function QuarterRow({ q }: { q: CarrierFinancialQuarter }) {
  const positive = q.net_profit_cr >= 0;
  return (
    <tr className="border-t border-hairline">
      <td className="py-2 pr-3 whitespace-nowrap font-medium text-ink">{q.quarter_label}</td>
      <td className="py-2 pr-3 whitespace-nowrap text-ink-secondary">{formatCrore(q.revenue_cr)}</td>
      <td className={"py-2 pr-3 whitespace-nowrap font-medium " + (positive ? "text-good" : "text-critical")}>
        {positive ? "+" : ""}
        {formatCrore(q.net_profit_cr)}
      </td>
      <td className={"py-2 pr-3 whitespace-nowrap font-medium " + (positive ? "text-good" : "text-critical")}>
        {q.net_margin_pct >= 0 ? "+" : ""}
        {q.net_margin_pct.toFixed(1)}%
      </td>
      <td className="py-2 text-ink-muted">
        <a href={q.source_url} target="_blank" rel="noreferrer" className="underline hover:text-ink-secondary">
          {q.filing_date}
        </a>
      </td>
    </tr>
  );
}

function CarrierCard({ ctx }: { ctx: CarrierFinancialContextData }) {
  if (!ctx.available) {
    return (
      <div className="rounded-xl border border-border bg-page/50 p-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-semibold text-ink">{ctx.carrier_name}</span>
          <span className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium bg-ink-muted/15 text-ink-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-ink-muted" aria-hidden />
            Not available
          </span>
        </div>
        <p className="text-sm text-ink-secondary">{ctx.reason}</p>
      </div>
    );
  }

  const quarters = [...ctx.quarters].sort((a, b) => a.period_start.localeCompare(b.period_start));

  return (
    <div className="rounded-xl border border-border p-4">
      <div className="font-semibold text-ink mb-2">{ctx.carrier_name}</div>
      <div className="scroll-fade-x overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-left text-ink-secondary">
              <th className="pb-1.5 pr-3 font-medium">Quarter</th>
              <th className="pb-1.5 pr-3 font-medium">Revenue (ops)</th>
              <th className="pb-1.5 pr-3 font-medium">Net profit/(loss)</th>
              <th className="pb-1.5 pr-3 font-medium">Margin</th>
              <th className="pb-1.5 font-medium">Filed</th>
            </tr>
          </thead>
          <tbody>
            {quarters.map((q) => (
              <QuarterRow key={q.quarter_label} q={q} />
            ))}
          </tbody>
        </table>
      </div>
      {ctx.compliance && (
        <p className="text-xs text-ink-muted mt-2" title={ctx.compliance.reason}>
          Investor-relations page ({ctx.compliance.domain}):{" "}
          {ctx.compliance.allowed ? "currently reachable under our compliance rules" : "currently not reachable under our compliance rules"}
        </p>
      )}
    </div>
  );
}

export function CarrierFinancialContext({ data }: { data: CarrierFinancialContextData[] | null }) {
  return (
    <Panel
      title="Airline financial context"
      subtitle="Each covered carrier's own publicly disclosed quarterly revenue, profit, and margin — real, dated figures from named public filings, never estimated. Akasa Air and Air India are privately held and file no public results, so they're marked not available rather than guessed at."
    >
      <div className="mb-4 rounded-lg bg-ink-muted/10 text-ink-secondary text-sm px-3 py-2.5 leading-relaxed">
        This is two real, separately-dated facts placed side by side — never a verdict. A carrier's quarterly,
        network-wide margin blends every route and three months of costs into one number; it cannot say whether
        any single route's single-day fare was "justified" or "unjustified," and nothing here computes that label.
      </div>

      {!data ? (
        <div className="h-16 flex items-center text-sm text-ink-muted">Checking disclosed financials…</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {data.map((ctx) => (
            <CarrierCard key={ctx.carrier_code} ctx={ctx} />
          ))}
        </div>
      )}
    </Panel>
  );
}
