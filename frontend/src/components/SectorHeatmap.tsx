import type { PriceGridCell, RouteOut } from "../api";
import { bookingLinkFor } from "../bookingLink";
import { addDaysISO, todayISO } from "../dateUtils";
import { AP_WINDOW_SHORT, apWindowFull, formatINR } from "../labels";
import { Panel } from "./Panel";
import { PriceLink } from "./PriceLink";

const AP_WINDOWS = Object.keys(AP_WINDOW_SHORT).map(Number);

function cellBackground(t: number): string {
  // t in [0,1]: 0 = cheapest in its row, 1 = priciest. Center (0.5) fades
  // to plain surface (reads as "typical"); extremes mix in the diverging
  // pole at up to 70% so the wash never overwhelms the number on top.
  const distance = Math.abs(t - 0.5) * 2;
  const pole = t < 0.5 ? "var(--color-diverge-cold)" : "var(--color-diverge-warm)";
  const pct = Math.round(distance * 70);
  return `color-mix(in oklab, ${pole} ${pct}%, var(--color-surface))`;
}

const CONFIDENCE_LABEL: Record<string, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

export function SectorHeatmap({
  cells,
  routeFilter,
  routeLookup,
}: {
  cells: PriceGridCell[];
  routeFilter: RouteOut | null;
  routeLookup: Record<string, RouteOut>;
}) {
  const visibleCells = routeFilter ? cells.filter((c) => c.route === routeFilter.display_name) : cells;
  const routes = Array.from(new Set(visibleCells.map((c) => c.route))).sort();

  if (routes.length === 0) {
    return (
      <Panel title="Prices by route and booking window" subtitle="How much a ticket cost, by how far ahead it was booked.">
        <div className="h-[160px] flex items-center justify-center text-sm text-ink-secondary">
          No prices collected for this route yet.
        </div>
      </Panel>
    );
  }

  const byRoute: Record<string, Record<number, PriceGridCell>> = {};
  for (const c of visibleCells) {
    byRoute[c.route] ??= {};
    byRoute[c.route][c.ap_window_days] = c;
  }

  const estimatedCount = visibleCells.filter((c) => c.is_estimated).length;

  return (
    <Panel
      title="Prices by route and booking window"
      subtitle="How much a ticket cost, by how far ahead it was booked. Blue = cheaper than usual for that route, red = pricier — always compared within its own row, never across routes."
    >
      <div className="scroll-fade-x overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr>
              <th className="text-left font-medium text-ink-secondary pb-2 pr-3">Route</th>
              {AP_WINDOWS.map((w) => (
                <th key={w} className="text-center font-medium text-ink-secondary pb-2 px-1" title={apWindowFull(w)}>
                  {AP_WINDOW_SHORT[w]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {routes.map((route) => {
              const row = byRoute[route] ?? {};
              const rowFares = AP_WINDOWS.map((w) => row[w]?.mean_fare).filter((v): v is number => v != null);
              const min = Math.min(...rowFares);
              const max = Math.max(...rowFares);
              return (
                <tr key={route}>
                  <td className="pr-3 py-1 whitespace-nowrap font-medium text-ink">{route}</td>
                  {AP_WINDOWS.map((w) => {
                    const cell = row[w];
                    if (!cell) {
                      return (
                        <td key={w} className="text-center py-1 px-1 text-ink-muted">
                          —
                        </td>
                      );
                    }
                    const t = max > min ? (cell.mean_fare - min) / (max - min) : 0.5;
                    const background = cellBackground(t);
                    const route = routeLookup[cell.route];
                    // Same "if searched today" convention the estimation engine
                    // itself uses for this ap_window_days - see basket_price_grid
                    // in the backend - so a linked search targets the exact date
                    // an estimate (or the real cell's own average window) implies.
                    const travelDate = addDaysISO(todayISO(), w);
                    // Never pass a carrier here: even a "real" cell pools
                    // whatever carriers/fare classes reported for this
                    // route/window, never attributable to one airline.
                    const link = route
                      ? bookingLinkFor({ origin: route.origin, destination: route.destination, travelDate })
                      : null;
                    const tooltip = cell.is_estimated
                      ? `Estimated · ${CONFIDENCE_LABEL[cell.confidence ?? "low"]} · ${cell.basis} · likely range ${formatINR(cell.range_low ?? 0)}–${formatINR(cell.range_high ?? 0)}${link ? ` · ${link.label} ↗` : ""}`
                      : `${apWindowFull(w)} · cheapest of ${cell.sample_size} real price${cell.sample_size === 1 ? "" : "s"} found${link ? ` · ${link.label} ↗` : ""}`;
                    return (
                      <td key={w} className="text-center py-1 px-1">
                        <PriceLink
                          href={link?.url ?? null}
                          label={link?.label ?? "Check current prices"}
                          className={
                            "relative block rounded-lg py-1.5 px-1 tabular-nums font-medium text-ink " +
                            (cell.is_estimated ? "border border-dashed border-ink-muted/50 opacity-80" : "")
                          }
                          style={{
                            background: cell.is_estimated
                              ? `repeating-linear-gradient(45deg, transparent 0 5px, color-mix(in oklab, var(--color-ink) 8%, transparent) 5px 10px), ${background}`
                              : background,
                          }}
                        >
                          <span title={tooltip}>
                            {cell.is_estimated && <span className="text-ink-muted mr-0.5">~</span>}
                            {formatINR(cell.mean_fare)}
                          </span>
                        </PriceLink>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-4 mt-4 text-xs text-ink-muted">
        <div className="flex items-center gap-2">
          <span>Cheaper</span>
          <span
            className="h-2 w-32 rounded-full"
            style={{
              background:
                "linear-gradient(to right, color-mix(in oklab, var(--color-diverge-cold) 70%, var(--color-surface)), var(--color-surface), color-mix(in oklab, var(--color-diverge-warm) 70%, var(--color-surface)))",
            }}
          />
          <span>Pricier</span>
        </div>
        {estimatedCount > 0 && (
          <div className="flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded border border-dashed border-ink-muted/50"
              style={{
                background:
                  "repeating-linear-gradient(45deg, transparent 0 3px, color-mix(in oklab, var(--color-ink) 8%, transparent) 3px 6px), var(--color-surface)",
              }}
              aria-hidden
            />
            <span>~ Estimated ({estimatedCount} cell{estimatedCount === 1 ? "" : "s"}) — not a real collected price</span>
          </div>
        )}
        <span>Click a price to check current results for that date</span>
      </div>
    </Panel>
  );
}
