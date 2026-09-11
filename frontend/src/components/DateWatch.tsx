import { useEffect, useMemo, useRef, useState } from "react";
import { api, type DateWatch as DateWatchData, type DateWatchCheckpoint, type RouteOut } from "../api";
import { bookingLinkFor } from "../bookingLink";
import { addDaysISO, todayISO } from "../dateUtils";
import { apWindowFull, apWindowShort, formatINR } from "../labels";
import { Panel } from "./Panel";
import { PriceLink } from "./PriceLink";
import { useUrlState } from "../urlState";

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function formatDateLabel(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

const STATUS_STYLE: Record<DateWatchCheckpoint["status"], { label: string; classes: string }> = {
  collected: { label: "", classes: "border-good/40 bg-good/10" },
  sold_out: { label: "Sold out that day", classes: "border-warning/40 bg-warning/10" },
  missed: { label: "Not checked (before we started tracking this date)", classes: "border-border bg-page opacity-70" },
  checking_today: { label: "Checking today…", classes: "border-good/40 bg-good/10" },
  upcoming: { label: "Not checked yet", classes: "border-border bg-page" },
};

// Shorter context phrase shown alongside an *estimated* price, where the
// full STATUS_STYLE label above would read redundantly ("Estimated · Not
// checked yet" reads fine; "Estimated · Not checked (before we started
// tracking this date)" doesn't).
const ESTIMATED_CONTEXT_LABEL: Partial<Record<DateWatchCheckpoint["status"], string>> = {
  missed: "before we started tracking this date",
  checking_today: "checking today for the real price",
  upcoming: "not checked yet",
};

const CONFIDENCE_LABEL: Record<string, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

function CheckpointRow({
  checkpoint,
  route,
  travelDate,
}: {
  checkpoint: DateWatchCheckpoint;
  route: RouteOut | undefined;
  travelDate: string;
}) {
  const style = STATUS_STYLE[checkpoint.status];
  const showEstimate = checkpoint.status !== "collected" && checkpoint.is_estimated && checkpoint.mean_fare != null;
  const hasPrice = checkpoint.status === "collected" || showEstimate;

  const link =
    hasPrice && route ? bookingLinkFor({ origin: route.origin, destination: route.destination, travelDate }) : null;
  const tooltip = showEstimate
    ? `Estimated · ${CONFIDENCE_LABEL[checkpoint.confidence ?? "low"]} · ${checkpoint.basis} · likely range ${formatINR(checkpoint.range_low ?? 0)}–${formatINR(checkpoint.range_high ?? 0)}${link ? ` · ${link.label} ↗` : ""}`
    : checkpoint.status === "collected"
      ? `Cheapest of ${checkpoint.sample_size} real price${checkpoint.sample_size === 1 ? "" : "s"} found for this checkpoint${link ? ` · ${link.label} ↗` : ""}`
      : link
        ? `${link.label} ↗`
        : undefined;

  return (
    <div
      className={
        "rounded-xl border p-3 flex-1 min-w-[130px] " +
        (showEstimate ? "border-dashed border-ink-muted/50" : style.classes)
      }
      style={
        showEstimate
          ? {
              background:
                "repeating-linear-gradient(45deg, transparent 0 5px, color-mix(in oklab, var(--color-ink) 8%, transparent) 5px 10px), var(--color-page)",
            }
          : undefined
      }
    >
      <div className="text-sm font-semibold text-ink" title={apWindowFull(checkpoint.ap_window_days)}>
        {apWindowShort(checkpoint.ap_window_days)} ahead
      </div>
      <div className="text-xs text-ink-muted mt-0.5">{formatDateLabel(checkpoint.checkpoint_date)}</div>
      {checkpoint.status === "collected" ? (
        <>
          <div className="text-base font-semibold text-ink mt-1.5">
            <PriceLink href={link?.url ?? null} label={link?.label ?? "Check current prices"}>
              <span title={tooltip}>{formatINR(checkpoint.min_fare ?? checkpoint.mean_fare ?? 0)}</span>
            </PriceLink>
          </div>
          <div className="text-xs text-ink-muted">
            cheapest of {checkpoint.sample_size} price{checkpoint.sample_size === 1 ? "" : "s"} found
          </div>
        </>
      ) : showEstimate ? (
        <>
          <div className="text-base font-semibold text-ink mt-1.5">
            <PriceLink href={link?.url ?? null} label={link?.label ?? "Check current prices"}>
              <span title={tooltip}>
                <span className="text-ink-muted mr-0.5">~</span>
                {formatINR(checkpoint.mean_fare ?? 0)}
              </span>
            </PriceLink>
          </div>
          <div className="text-xs text-ink-muted leading-relaxed">
            Estimated — {ESTIMATED_CONTEXT_LABEL[checkpoint.status] ?? "not a real price yet"}
          </div>
        </>
      ) : (
        <div className="text-xs text-ink-secondary mt-1.5 leading-relaxed">{style.label}</div>
      )}
    </div>
  );
}

export function DateWatch({ routes }: { routes: RouteOut[] }) {
  const min = useMemo(() => addDaysISO(todayISO(), 1), []);
  const max = useMemo(() => addDaysISO(todayISO(), 45), []);

  // The URL is the shareable/bookmarkable record of what's selected;
  // routeId/date below stay the actual source of truth the rest of this
  // component already reads and drives (including the clock-skew
  // auto-adjustment further down) - a separate effect mirrors them into
  // these params rather than routing every read through the URL, so nothing
  // about the existing fetch/retry logic has to change.
  const [tripRouteParam, setTripRouteParam] = useUrlState("tripRoute", null);
  const [tripDateParam, setTripDateParam] = useUrlState("tripDate", null);

  const [routeId, setRouteId] = useState<number | "">(() => {
    if (!tripRouteParam) return "";
    const id = Number(tripRouteParam);
    return routes.some((r) => r.id === id) ? id : "";
  });
  const [date, setDate] = useState<string>(() => {
    if (tripDateParam && ISO_DATE_RE.test(tripDateParam) && tripDateParam >= min && tripDateParam <= max) {
      return tripDateParam;
    }
    return min;
  });
  const [result, setResult] = useState<DateWatchData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const clockSkewRetries = useRef(0);

  const sortedRoutes = [...routes].sort((a, b) => a.display_name.localeCompare(b.display_name));
  const selectedRoute = routes.find((r) => r.id === routeId);

  useEffect(() => {
    setTripRouteParam(routeId ? String(routeId) : null);
  }, [routeId, setTripRouteParam]);

  useEffect(() => {
    // Only worth recording a date once a route is actually picked - an
    // untouched date field defaulting to "tomorrow" isn't a real
    // selection worth carrying into a bookmark.
    setTripDateParam(routeId ? date : null);
  }, [routeId, date, setTripDateParam]);

  useEffect(() => {
    if (!routeId) {
      setResult(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .dateWatch(routeId, date)
      .then((r) => {
        if (cancelled) return;
        clockSkewRetries.current = 0;
        setResult(r);
      })
      .catch((e) => {
        if (cancelled) return;
        // Our device's clock and the server's clock can disagree by a day
        // (a real thing that can happen on any machine, not a bug) - if the
        // server says our chosen date is now in the past, nudge forward and
        // retry a couple of times instead of showing a confusing error.
        const isPastDateError = e instanceof Error && e.message.includes("400");
        if (isPastDateError && clockSkewRetries.current < 3) {
          clockSkewRetries.current += 1;
          setDate((d) => addDaysISO(d, 1));
          return;
        }
        // Any other failure (most commonly: the backend server is still
        // starting up, or isn't running) - offer a way to recover instead
        // of a dead-end message, since this is genuinely recoverable most
        // of the time (just wait a moment and retry).
        setError("Couldn't check that date right now — the server may still be starting up, or the connection dropped.");
        setResult(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [routeId, date, retryTick]);

  return (
    <Panel
      title="Track your trip"
      subtitle="Pick a route and the exact date you want to fly — we'll show every real price we've found for that day, and the cheapest one so far, so you know when to book. Click any price to check current results for that date."
    >
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <select
          value={routeId}
          onChange={(e) => setRouteId(e.target.value ? Number(e.target.value) : "")}
          className="text-sm px-3 py-1.5 rounded-lg border border-border bg-surface text-ink cursor-pointer"
        >
          <option value="">Choose a route…</option>
          {sortedRoutes.map((r) => (
            <option key={r.id} value={r.id}>
              {r.display_name}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={date}
          min={min}
          max={max}
          onChange={(e) => setDate(e.target.value)}
          className="text-sm px-3 py-1.5 rounded-lg border border-border bg-surface text-ink"
        />
        <span className="text-xs text-ink-muted">We can only track dates within the next 45 days</span>
      </div>

      {!routeId ? (
        <p className="text-sm text-ink-secondary">Pick a route and a date above to start tracking.</p>
      ) : loading && !result ? (
        <div className="h-16 flex items-center text-sm text-ink-muted">Checking real prices for this date…</div>
      ) : error ? (
        <div className="flex items-center gap-3">
          <p className="text-sm text-critical">{error}</p>
          <button
            onClick={() => setRetryTick((t) => t + 1)}
            className="text-sm px-3 py-1 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors shrink-0"
          >
            Try again
          </button>
        </div>
      ) : result ? (
        <div className="flex flex-col gap-4">
          <div>
            <p className="text-[15px] text-ink leading-relaxed max-w-2xl">{result.message}</p>
            {result.has_signal && result.cheapest_so_far && result.priciest_so_far && (
              <div className="flex flex-wrap gap-6 text-sm text-ink-secondary mt-2">
                <div>
                  <div className="text-ink-muted text-xs">Cheapest so far</div>
                  <div className="font-semibold text-ink">
                    <PriceLink
                      href={
                        selectedRoute
                          ? bookingLinkFor({
                              origin: selectedRoute.origin,
                              destination: selectedRoute.destination,
                              travelDate: result.travel_date,
                            }).url
                          : null
                      }
                      label="Check current prices"
                    >
                      {formatINR(result.cheapest_so_far.min_fare ?? result.cheapest_so_far.mean_fare ?? 0)}
                    </PriceLink>{" "}
                    <span className="font-normal text-ink-secondary">
                      ({apWindowShort(result.cheapest_so_far.ap_window_days)} ahead)
                    </span>
                  </div>
                </div>
                <div>
                  <div className="text-ink-muted text-xs">Priciest so far</div>
                  <div className="font-semibold text-ink">
                    <PriceLink
                      href={
                        selectedRoute
                          ? bookingLinkFor({
                              origin: selectedRoute.origin,
                              destination: selectedRoute.destination,
                              travelDate: result.travel_date,
                            }).url
                          : null
                      }
                      label="Check current prices"
                    >
                      {formatINR(result.priciest_so_far.min_fare ?? result.priciest_so_far.mean_fare ?? 0)}
                    </PriceLink>{" "}
                    <span className="font-normal text-ink-secondary">
                      ({apWindowShort(result.priciest_so_far.ap_window_days)} ahead)
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-3">
            {result.checkpoints.map((c) => (
              <CheckpointRow key={c.ap_window_days} checkpoint={c} route={selectedRoute} travelDate={result.travel_date} />
            ))}
          </div>

          {result.checkpoints.some((c) => c.status !== "collected" && c.is_estimated) && (
            <div className="flex items-center gap-1.5 text-xs text-ink-muted">
              <span
                className="inline-block h-3 w-3 rounded border border-dashed border-ink-muted/50"
                style={{
                  background:
                    "repeating-linear-gradient(45deg, transparent 0 3px, color-mix(in oklab, var(--color-ink) 8%, transparent) 3px 6px), var(--color-page)",
                }}
                aria-hidden
              />
              <span>~ Estimated — not a real price we've collected for this date. Hover a box for how it's worked out.</span>
            </div>
          )}
        </div>
      ) : null}
    </Panel>
  );
}
