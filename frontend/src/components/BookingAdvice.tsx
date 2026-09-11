import type { BookingAdvice as BookingAdviceData, RouteOut } from "../api";
import { bookingLinkFor } from "../bookingLink";
import { addDaysISO, todayISO } from "../dateUtils";
import { apWindowShort, formatINR } from "../labels";
import { Panel } from "./Panel";
import { PriceLink } from "./PriceLink";

const VERDICT_STYLE: Record<string, { badge: string; label: string }> = {
  book_early: { badge: "bg-warning/20 text-ink", label: "Book early" },
  can_wait: { badge: "bg-good/15 text-good", label: "No need to rush" },
  no_strong_pattern: { badge: "bg-ink-muted/15 text-ink-muted", label: "No strong pattern" },
};

const CONFIDENCE_LABEL: Record<string, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence — still early data",
};

export function BookingAdvice({
  advice,
  route,
  loading,
}: {
  advice: BookingAdviceData | null;
  route: RouteOut | null;
  loading: boolean;
}) {
  if (!route) {
    return (
      <Panel title="Best time to book">
        <p className="text-sm text-ink-secondary">
          Pick a route above to see whether prices have favoured booking early or booking last-minute.
        </p>
      </Panel>
    );
  }

  return (
    <Panel
      title="Best time to book"
      subtitle={`Based on real prices we've collected for ${route.display_name} at different booking windows.`}
    >
      {loading || !advice ? (
        <div className="h-16 flex items-center text-sm text-ink-muted">Checking real prices for this route…</div>
      ) : !advice.has_signal ? (
        <p className="text-sm text-ink-secondary">{advice.message}</p>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={
                "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium " +
                (VERDICT_STYLE[advice.verdict ?? ""]?.badge ?? "bg-ink-muted/15 text-ink-muted")
              }
            >
              {VERDICT_STYLE[advice.verdict ?? ""]?.label ?? "Verdict"}
            </span>
            {advice.confidence && (
              <span className="text-xs text-ink-muted">{CONFIDENCE_LABEL[advice.confidence]}</span>
            )}
          </div>

          <p className="text-[15px] text-ink leading-relaxed max-w-2xl">{advice.message}</p>

          {advice.cheapest_window_days != null && advice.priciest_window_days != null && (
            <div className="flex flex-wrap gap-6 text-sm text-ink-secondary">
              <div>
                <div className="text-ink-muted text-xs">Cheapest so far</div>
                <div className="font-semibold text-ink">
                  <PriceLink
                    href={
                      bookingLinkFor({
                        origin: route.origin,
                        destination: route.destination,
                        travelDate: addDaysISO(todayISO(), advice.cheapest_window_days),
                      }).url
                    }
                    label="Check current prices"
                  >
                    {formatINR(advice.cheapest_mean_fare ?? 0)}
                  </PriceLink>{" "}
                  <span className="font-normal text-ink-secondary">
                    ({apWindowShort(advice.cheapest_window_days)} ahead)
                  </span>
                </div>
              </div>
              <div>
                <div className="text-ink-muted text-xs">Priciest so far</div>
                <div className="font-semibold text-ink">
                  <PriceLink
                    href={
                      bookingLinkFor({
                        origin: route.origin,
                        destination: route.destination,
                        travelDate: addDaysISO(todayISO(), advice.priciest_window_days),
                      }).url
                    }
                    label="Check current prices"
                  >
                    {formatINR(advice.priciest_mean_fare ?? 0)}
                  </PriceLink>{" "}
                  <span className="font-normal text-ink-secondary">
                    ({apWindowShort(advice.priciest_window_days)} ahead)
                  </span>
                </div>
              </div>
            </div>
          )}

          <p className="text-xs text-ink-muted">
            Based on {advice.windows_with_data} of 5 booking windows with real data — a historical pattern, not a
            guarantee. Click a price to check current results for that booking window.
          </p>
        </div>
      )}
    </Panel>
  );
}
