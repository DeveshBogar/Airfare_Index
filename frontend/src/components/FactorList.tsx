import type { PossibleFactor } from "../api";
import { NEWS_CATEGORY_LABEL } from "../labels";

// Shared by the flag detail row and the draft notice, which both need to
// render the same heterogeneous factor list the backend returns.
//
// Each factor is displayed on its own terms with its own citation. They are
// deliberately NOT ranked, scored, or combined — see
// app/index/anomaly_detection.py::why_context_for_flag. A festival window, a
// fuel-price story, and a carrier's last disclosed margin are three separate
// real facts; deciding which (if any) explains a fare is the reader's job.
export function FactorList({ factors }: { factors: PossibleFactor[] }) {
  if (factors.length === 0) {
    return <p className="text-sm text-ink-secondary">No correlating factors found in the data we hold.</p>;
  }

  return (
    <ul className="flex flex-col gap-2">
      {factors.map((factor, i) => (
        <li key={`${factor.factor_type}-${i}`} className="text-sm">
          {renderFactor(factor)}
        </li>
      ))}
    </ul>
  );
}

function renderFactor(factor: PossibleFactor) {
  if (factor.factor_type === "festival_demand_window") {
    return (
      <div className="rounded-lg border border-hairline px-3 py-2">
        <Chip>Travel demand</Chip>
        <div className="font-medium text-ink mt-1">{String(factor.window_name)}</div>
        <div className="text-ink-secondary">
          {String(factor.start)} to {String(factor.end)} — {String(factor.why)}
        </div>
        <div className="text-xs text-ink-muted mt-1">{String(factor.source_note ?? "")}</div>
      </div>
    );
  }

  if (factor.factor_type === "news_item") {
    const categories = (factor.categories as string[] | undefined) ?? [];
    return (
      <div className="rounded-lg border border-hairline px-3 py-2">
        {categories.map((c) => (
          <Chip key={c}>{NEWS_CATEGORY_LABEL[c] ?? c}</Chip>
        ))}
        <div className="mt-1">
          <a
            href={String(factor.link)}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-ink hover:underline"
          >
            {String(factor.title)}
          </a>
        </div>
        <div className="text-xs text-ink-muted mt-0.5">
          {String(factor.source)} · {String(factor.published_at).slice(0, 10)}
        </div>
      </div>
    );
  }

  if (factor.factor_type === "carrier_financial_context") {
    const latest = factor.latest_quarter as
      | { quarter_label: string; net_margin_pct: number; filing_date: string; source_url: string }
      | null
      | undefined;
    return (
      <div className="rounded-lg border border-hairline px-3 py-2">
        <Chip>Carrier financials</Chip>
        {factor.available && latest ? (
          <div className="mt-1 text-ink-secondary">
            Last disclosed net margin:{" "}
            <span className={"font-medium " + (latest.net_margin_pct >= 0 ? "text-good" : "text-critical")}>
              {latest.net_margin_pct >= 0 ? "+" : ""}
              {latest.net_margin_pct.toFixed(1)}%
            </span>{" "}
            ({latest.quarter_label}, filed{" "}
            <a href={latest.source_url} target="_blank" rel="noreferrer" className="underline hover:text-ink">
              {latest.filing_date}
            </a>
            ). A quarterly, network-wide figure — it cannot validate or invalidate any single fare.
          </div>
        ) : (
          <div className="mt-1 text-ink-secondary">{String(factor.reason ?? "Not available.")}</div>
        )}
      </div>
    );
  }

  return <div className="text-ink-secondary">{JSON.stringify(factor)}</div>;
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full bg-series-1/10 text-series-1 px-2 py-0.5 text-[11px] font-medium mr-1.5">
      {children}
    </span>
  );
}
