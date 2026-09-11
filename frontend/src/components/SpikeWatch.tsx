import { useEffect, useMemo, useState } from "react";
import { api, type FestivalRoutePrice, type FestivalRoutePrices, type RouteOut, type SpikeCalendarWindow } from "../api";
import { bookingLinkFor } from "../bookingLink";
import { formatINR } from "../labels";
import { Panel } from "./Panel";
import { PriceLink } from "./PriceLink";
import { useUrlState } from "../urlState";

function formatDateRange(start: string, end: string): string {
  const fmt = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  return `${fmt(start)} – ${fmt(end)}`;
}

const CONFIDENCE_LABEL: Record<string, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

function CalendarChip({ window, selected, onClick }: { window: SpikeCalendarWindow; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={
        "text-left rounded-xl border p-3 flex-1 min-w-[180px] transition-colors cursor-pointer " +
        (selected
          ? "border-series-1 ring-1 ring-series-1 bg-surface-raised"
          : window.in_scraping_horizon
            ? "border-good/40 bg-good/10 hover:border-good/70"
            : "border-border bg-page hover:border-ink-muted/50")
      }
    >
      <div className="flex items-center gap-1.5">
        {window.in_scraping_horizon && <span className="h-1.5 w-1.5 rounded-full bg-good" aria-hidden />}
        <span className="text-sm font-semibold text-ink">{window.name}</span>
      </div>
      <div className="text-xs text-ink-secondary mt-0.5">{formatDateRange(window.start, window.end)}</div>
      <div className="text-xs text-ink-muted mt-1 leading-relaxed">{window.why}</div>
      <div className="flex items-center gap-2 mt-1.5">
        {window.in_scraping_horizon && <span className="text-xs text-good font-medium">Watching now</span>}
        <span className="text-xs text-series-1 font-medium">{selected ? "Hide details ▲" : "See details ▼"}</span>
      </div>
    </button>
  );
}

// Both sides of a route's comparison (the festival-window price and the
// ordinary-day baseline) are independently either real or estimated —
// this reduces that pair down to one honest, three-way label rather than
// a binary real/estimated that would overstate confidence on a mixed row.
function sourceBadge(row: FestivalRoutePrice): { label: string; className: string } {
  if (!row.is_estimated && !row.baseline_is_estimated) {
    return { label: "Real", className: "bg-good/15 text-good" };
  }
  if (row.is_estimated && row.baseline_is_estimated) {
    return { label: "Estimated", className: "bg-ink-muted/15 text-ink-muted" };
  }
  return { label: "Partly estimated", className: "bg-warning/25 text-ink" };
}

function changeTooltip(row: FestivalRoutePrice, windowName: string): string {
  const festivalSide = row.is_estimated
    ? `${windowName} price: estimated${row.confidence ? ` (${CONFIDENCE_LABEL[row.confidence]})` : ""}${row.basis ? ` — ${row.basis}` : ""}`
    : `${windowName} price: real, from ${row.sample_size} collected fare${row.sample_size === 1 ? "" : "s"}`;
  const baselineSide =
    row.baseline_is_estimated || row.baseline_price == null
      ? "Ordinary-day price: estimated — this route's own real fares only, with no festival adjustment applied"
      : `Ordinary-day price: real, from ${row.baseline_sample_size} collected fare${row.baseline_sample_size === 1 ? "" : "s"} on non-spike dates`;
  return `${festivalSide} · ${baselineSide}`;
}

function ChangeRow({
  row,
  windowName,
  windowStart,
  route,
}: {
  row: FestivalRoutePrice;
  windowName: string;
  windowStart: string;
  route: RouteOut | undefined;
}) {
  if (row.pct_change == null || row.baseline_price == null) return null;
  const pricier = row.pct_change > 0;
  const abs = Math.abs(row.pct_change);
  const negligible = abs < 5;
  const badge = sourceBadge(row);

  const priceLink = route ? bookingLinkFor({ origin: route.origin, destination: route.destination, travelDate: windowStart }) : null;
  // The baseline is "an ordinary day" by definition - it has no single
  // date to search for, so the link searches the route with dates left
  // open rather than implying one specific day.
  const baselineLink = route ? bookingLinkFor({ origin: route.origin, destination: route.destination }) : null;

  return (
    <div
      className="flex items-center justify-between gap-4 py-2.5 border-t border-hairline first:border-t-0"
      title={changeTooltip(row, windowName)}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-ink">{row.route}</span>
          <span className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full shrink-0 ${badge.className}`}>
            {badge.label}
          </span>
        </div>
        <div className="text-xs text-ink-secondary mt-0.5">
          <PriceLink href={priceLink?.url ?? null} label={priceLink?.label ?? "Check current prices"}>
            {row.is_estimated && <span className="text-ink-muted">~</span>}
            {formatINR(row.price)}
          </PriceLink>{" "}
          for {windowName} dates vs.{" "}
          <PriceLink href={baselineLink?.url ?? null} label={baselineLink?.label ?? "Check current prices"}>
            {row.baseline_is_estimated && <span className="text-ink-muted">~</span>}
            {formatINR(row.baseline_price)}
          </PriceLink>{" "}
          other days
        </div>
      </div>
      <div
        className={
          "shrink-0 text-sm font-semibold whitespace-nowrap " +
          (negligible ? "text-ink-muted" : pricier ? "text-critical" : "text-success-text")
        }
      >
        {negligible ? "About the same" : pricier ? `▲ ${abs.toFixed(0)}% pricier` : `▼ ${abs.toFixed(0)}% cheaper`}
      </div>
    </div>
  );
}

function FestivalPriceRow({ row, windowStart, route }: { row: FestivalRoutePrice; windowStart: string; route: RouteOut | undefined }) {
  const link = route ? bookingLinkFor({ origin: route.origin, destination: route.destination, travelDate: windowStart }) : null;
  const tooltip =
    (row.is_estimated
      ? `Estimated · ${CONFIDENCE_LABEL[row.confidence ?? "low"]} · ${row.basis} · likely range ${formatINR(row.range_low ?? 0)}–${formatINR(row.range_high ?? 0)}`
      : `Real price · ${row.sample_size} ticket${row.sample_size === 1 ? "" : "s"} found for this window`) +
    (link ? ` · ${link.label} ↗` : "");

  return (
    <tr className="border-t border-hairline">
      <td className="py-2 pr-3 font-medium text-ink whitespace-nowrap">{row.route}</td>
      <td className="py-2 text-right tabular-nums font-medium text-ink whitespace-nowrap">
        <PriceLink href={link?.url ?? null} label={link?.label ?? "Check current prices"} className="text-ink">
          <span title={tooltip}>
            {row.is_estimated && <span className="text-ink-muted mr-0.5">~</span>}
            {formatINR(row.price)}
          </span>
        </PriceLink>
      </td>
      <td className="py-2 pl-3 text-xs text-ink-muted whitespace-nowrap">
        {row.is_estimated ? "Estimated" : `${row.sample_size} real price${row.sample_size === 1 ? "" : "s"}`}
      </td>
    </tr>
  );
}

function FestivalPricesPanel({ data, routeLookup }: { data: FestivalRoutePrices; routeLookup: Record<string, RouteOut> }) {
  const estimatedCount = data.routes.filter((r) => r.is_estimated).length;

  return (
    <div className="rounded-xl border border-border bg-page/50 p-4">
      <div className="text-sm font-semibold text-ink mb-0.5">
        Ticket prices for {data.window_name} ({formatDateRange(data.start, data.end)})
      </div>
      <p className="text-xs text-ink-secondary mb-3">
        Real prices where we've collected fares for these dates, a clearly-marked estimate otherwise. Click a price to check
        current results for these dates.
      </p>
      <div className="scroll-fade-x overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-ink-secondary">
              <th className="pb-2 pr-3 font-medium">Route</th>
              <th className="pb-2 font-medium text-right">Price</th>
              <th className="pb-2 pl-3 font-medium">Source</th>
            </tr>
          </thead>
          <tbody>
            {data.routes.map((row) => (
              <FestivalPriceRow key={row.route} row={row} windowStart={data.start} route={routeLookup[row.route]} />
            ))}
          </tbody>
        </table>
      </div>
      {estimatedCount > 0 && (
        <p className="text-xs text-ink-muted mt-3">
          ~ Estimated — not a real price collected for these exact dates. Hover a row for how it's worked out.
        </p>
      )}
    </div>
  );
}

export function SpikeWatch({
  calendar,
  routeLookup,
}: {
  calendar: SpikeCalendarWindow[];
  routeLookup: Record<string, RouteOut>;
}) {
  // The URL is the shareable/bookmarkable record of which festival is
  // selected - honoring a valid ?festival= key on load (falling back to
  // the usual "nearest upcoming window" default for an invalid/missing
  // one), and staying in sync afterward via the effect below.
  const [festivalParam, setFestivalParam] = useUrlState("festival", null);
  const [selectedKey, setSelectedKey] = useState<string | null>(() => {
    if (festivalParam && calendar.some((w) => w.key === festivalParam)) {
      return festivalParam;
    }
    return calendar.find((w) => w.in_scraping_horizon)?.key ?? calendar[0]?.key ?? null;
  });
  const [prices, setPrices] = useState<FestivalRoutePrices | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);

  useEffect(() => {
    setFestivalParam(selectedKey);
  }, [selectedKey, setFestivalParam]);

  useEffect(() => {
    if (!selectedKey) {
      setPrices(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .festivalRoutePrices(selectedKey)
      .then((r) => {
        if (!cancelled) setPrices(r);
      })
      .catch(() => {
        if (!cancelled) {
          setError("Couldn't load prices for this window right now.");
          setPrices(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedKey, retryTick]);

  const changeRows = useMemo(() => {
    if (!prices) return [];
    return [...prices.routes]
      .filter((r) => r.pct_change != null)
      .sort((a, b) => Math.abs(b.pct_change ?? 0) - Math.abs(a.pct_change ?? 0));
  }, [prices]);

  const anyEstimatedInChange = changeRows.some((r) => r.is_estimated || r.baseline_is_estimated);

  return (
    <Panel
      title="Festival & wedding-season price watch"
      subtitle="Pick a festival to see every route's price change vs. an ordinary day, and the full price list below it — real where we've collected fares for those exact dates, a clearly-flagged estimate otherwise."
    >
      <div className="flex flex-wrap gap-3 mb-4">
        {calendar.map((w) => (
          <CalendarChip
            key={w.key}
            window={w}
            selected={selectedKey === w.key}
            onClick={() => setSelectedKey((prev) => (prev === w.key ? null : w.key))}
          />
        ))}
      </div>

      {!selectedKey && <p className="text-sm text-ink-secondary">Select a card above to see its price comparison.</p>}

      {selectedKey && loading && !prices && (
        <div className="h-16 flex items-center text-sm text-ink-muted">Checking prices for this window…</div>
      )}

      {selectedKey && error && (
        <div className="flex items-center gap-3">
          <p className="text-sm text-critical">{error}</p>
          <button
            onClick={() => setRetryTick((t) => t + 1)}
            className="text-sm px-3 py-1 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors shrink-0"
          >
            Try again
          </button>
        </div>
      )}

      {selectedKey && prices && (
        <>
          <div className="mb-4">
            {changeRows.length === 0 ? (
              <p className="text-sm text-ink-secondary">Not enough data yet to compare this window's routes.</p>
            ) : (
              <>
                <div>
                  {changeRows.map((row) => (
                    <ChangeRow
                      key={row.route}
                      row={row}
                      windowName={prices.window_name}
                      windowStart={prices.start}
                      route={routeLookup[row.route]}
                    />
                  ))}
                </div>
                {anyEstimatedInChange && (
                  <p className="text-xs text-ink-muted mt-3">
                    ~ Estimated — not a real price collected for that side of the comparison. Hover a row for how it's worked
                    out. "Partly estimated" means only one side (the festival price or the ordinary-day baseline) is real.
                  </p>
                )}
              </>
            )}
          </div>

          <FestivalPricesPanel data={prices} routeLookup={routeLookup} />
        </>
      )}
    </Panel>
  );
}
