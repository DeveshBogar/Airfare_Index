import type { FareQuote, RouteOut } from "../api";
import { bookingLinkFor } from "../bookingLink";
import { apWindowFull, formatINR } from "../labels";
import { Panel } from "./Panel";
import { PriceLink } from "./PriceLink";

export function FaresTable({
  rows,
  routeFilter,
  routeLookup,
}: {
  rows: FareQuote[];
  routeFilter: RouteOut | null;
  routeLookup: Record<string, RouteOut>;
}) {
  const visible = routeFilter ? rows.filter((r) => r.route === routeFilter.display_name) : rows;

  return (
    <Panel
      title="Recent prices found"
      subtitle="The latest individual ticket prices collected, most recent first. Click a price to check it on the airline's own site — real fares change constantly, so it may not match exactly."
    >
      <div className="scroll-fade-x overflow-x-auto max-h-[340px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface">
            <tr className="text-left text-ink-secondary">
              <th className="pb-2 pr-3 font-medium">Route</th>
              <th className="pb-2 pr-3 font-medium">Airline</th>
              <th className="pb-2 pr-3 font-medium">Booked</th>
              <th className="pb-2 pr-3 font-medium">Flying on</th>
              <th className="pb-2 pr-3 font-medium">Fare type</th>
              <th className="pb-2 font-medium text-right">Price</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => {
              const route = routeLookup[r.route];
              const link =
                !r.sold_out && r.total_fare != null && route
                  ? bookingLinkFor({
                      origin: route.origin,
                      destination: route.destination,
                      travelDate: r.travel_date,
                      carrierCode: r.carrier_code,
                    })
                  : null;
              return (
                <tr key={r.id} className="border-t border-hairline">
                  <td className="py-2 pr-3 whitespace-nowrap font-medium text-ink">{r.route}</td>
                  <td className="py-2 pr-3 text-ink-secondary">{r.carrier_code}</td>
                  <td className="py-2 pr-3 whitespace-nowrap text-ink-secondary" title={apWindowFull(r.ap_window_days)}>
                    {r.ap_window_days} day{r.ap_window_days === 1 ? "" : "s"} ahead
                  </td>
                  <td className="py-2 pr-3 whitespace-nowrap text-ink-secondary">{r.travel_date}</td>
                  <td className="py-2 pr-3 whitespace-nowrap capitalize text-ink-secondary">{r.fare_class}</td>
                  <td className="py-2 text-right tabular-nums font-medium text-ink">
                    {r.sold_out ? (
                      <span className="text-ink-muted font-normal">Sold out</span>
                    ) : r.total_fare != null ? (
                      <PriceLink href={link?.url ?? null} label={link?.label ?? "Check current prices"}>
                        {formatINR(r.total_fare)}
                      </PriceLink>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              );
            })}
            {visible.length === 0 && (
              <tr>
                <td colSpan={6} className="py-8 text-center text-ink-muted">
                  No prices collected for this route yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
