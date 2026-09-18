import { useState } from "react";
import { api, type FareQuote, type OperatorOverview, type RegulatorFlag, type RouteOut } from "../api";
import { formatINR } from "../labels";
import { CarrierIndexChart } from "./CarrierIndexChart";
import { FaresTable } from "./FaresTable";
import { Panel } from "./Panel";

// What an airline sees. Scoped to its own carrier by the server — there is
// no carrier selector here because there is no endpoint that would honour
// one. The market-wide headline index is shown alongside the carrier's own,
// because an index movement means nothing without it; per-competitor detail
// is deliberately absent.

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</div>
      <div className="text-[22px] font-semibold text-ink tabular-nums mt-1">{value}</div>
      {hint && <div className="text-xs text-ink-secondary mt-0.5">{hint}</div>}
    </div>
  );
}

export function AirlineDashboard({
  overview,
  flags,
  fares,
  routeLookup,
  loading,
  onResponded,
}: {
  overview: OperatorOverview | null;
  flags: RegulatorFlag[] | null;
  fares: FareQuote[] | null;
  routeLookup: Record<string, RouteOut>;
  loading: boolean;
  onResponded: () => void;
}) {
  if (loading && !overview) {
    return (
      <Panel title="Your airline">
        <div className="h-16 flex items-center text-sm text-ink-muted">Loading your carrier's data…</div>
      </Panel>
    );
  }

  if (!overview) {
    return (
      <Panel title="Your airline">
        <p className="text-sm text-ink-secondary">
          Couldn't load your carrier's data just now. Try refreshing.
        </p>
      </Panel>
    );
  }

  const movement =
    overview.latest_index_value != null ? overview.latest_index_value - 100 : null;

  return (
    <>
      <section className="card-shadow rounded-2xl border border-border bg-surface p-5">
        <h2 className="text-[15px] font-semibold text-ink">{overview.carrier_name} — operator view</h2>
        <p className="text-sm text-ink-secondary mt-0.5 max-w-3xl leading-relaxed">
          Your own collected fares, your own price index against the whole-market average, and any fares of
          yours that were statistically flagged for review. A flag is an observation with its method stated —
          not a finding of wrongdoing. You can file a written response to any of them, which the reviewing
          official sees alongside the flag.
        </p>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Tile
          label="Your index"
          value={overview.latest_index_value != null ? overview.latest_index_value.toFixed(1) : "—"}
          hint={
            movement != null
              ? `${movement >= 0 ? "+" : ""}${movement.toFixed(1)} vs base 100 · ${overview.latest_index_date}`
              : "Not enough history yet"
          }
        />
        <Tile
          label="Fares collected"
          value={overview.quotes_collected.toLocaleString("en-IN")}
          hint={`across ${overview.routes_covered} route${overview.routes_covered === 1 ? "" : "s"}`}
        />
        <Tile
          label="Flags raised"
          value={String(overview.flags_total)}
          hint={`${overview.flags_new} not yet reviewed`}
        />
        <Tile
          label="Awaiting your response"
          value={String(overview.flags_awaiting_response)}
          hint={overview.flags_awaiting_response === 0 ? "Nothing outstanding" : "Open flags with no reply filed"}
        />
      </div>

      <CarrierIndexChart
        data={{ headline: overview.headline, carriers: overview.index ? [overview.index] : [] }}
      />

      <AirlineFlags flags={flags} onResponded={onResponded} />

      <FaresTable rows={fares ?? []} routeFilter={null} routeLookup={routeLookup} />
    </>
  );
}

function AirlineFlags({
  flags,
  onResponded,
}: {
  flags: RegulatorFlag[] | null;
  onResponded: () => void;
}) {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle(flag: RegulatorFlag) {
    setError(null);
    if (expandedId === flag.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(flag.id);
    setDraft(flag.operator_response);
  }

  async function submit(flag: RegulatorFlag) {
    setBusy(true);
    setError(null);
    try {
      await api.respondToFlag(flag.id, draft);
      onResponded();
      setExpandedId(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="Flags raised against your fares"
      subtitle="Real fares of yours that came in both statistically unusual for their own route/booking-window history and materially above it. Filing a response records your account of the fare for the reviewing official; it does not change the flag's status, which only a regulator can do."
    >
      {!flags ? (
        <div className="h-12 flex items-center text-sm text-ink-muted">Loading flags…</div>
      ) : flags.length === 0 ? (
        <p className="text-sm text-ink-secondary">
          No flags raised against your fares. Flags appear only once a route and booking window has enough real
          daily history for an unusual day to stand out against it.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {error && (
            <div className="rounded-lg border border-border bg-warning/10 text-ink text-sm px-3 py-2">{error}</div>
          )}
          <div className="scroll-fade-x overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-ink-secondary">
                  <th className="pb-2 pr-3 font-medium">Route</th>
                  <th className="pb-2 pr-3 font-medium">Window</th>
                  <th className="pb-2 pr-3 font-medium">Observed</th>
                  <th className="pb-2 pr-3 font-medium">Baseline</th>
                  <th className="pb-2 pr-3 font-medium">Above</th>
                  <th className="pb-2 pr-3 font-medium">Seen on</th>
                  <th className="pb-2 pr-3 font-medium">Your response</th>
                  <th className="pb-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {flags.map((flag) => (
                  <tr key={flag.id} className="border-t border-hairline align-top">
                    <td className="py-2 pr-3 whitespace-nowrap font-medium text-ink">{flag.route}</td>
                    <td className="py-2 pr-3 whitespace-nowrap text-ink-secondary">T+{flag.ap_window_days}</td>
                    <td className="py-2 pr-3 whitespace-nowrap font-medium text-critical tabular-nums">
                      {formatINR(flag.observed_fare)}
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap text-ink-secondary tabular-nums">
                      {formatINR(flag.baseline_median_fare)}
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap font-medium text-critical tabular-nums">
                      +{flag.pct_above_baseline_median.toFixed(1)}%
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap text-ink-muted">{flag.flagged_search_date}</td>
                    <td className="py-2 pr-3 whitespace-nowrap">
                      {flag.operator_response ? (
                        <span className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium bg-good/15 text-good">
                          Filed
                        </span>
                      ) : (
                        <span className="text-xs text-ink-muted">Not yet</span>
                      )}
                    </td>
                    <td className="py-2">
                      <button
                        onClick={() => toggle(flag)}
                        className="text-xs px-2 py-1 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors whitespace-nowrap"
                      >
                        {expandedId === flag.id ? "Close" : flag.operator_response ? "Edit reply" : "Respond"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {expandedId != null &&
            (() => {
              const flag = flags.find((f) => f.id === expandedId);
              if (!flag) return null;
              return (
                <div className="rounded-xl border border-border p-4 mt-1">
                  <div className="text-sm font-semibold text-ink mb-1">
                    {flag.route} · T+{flag.ap_window_days} · {flag.flagged_search_date}
                  </div>
                  <p className="text-sm text-ink-secondary mb-3">
                    {formatINR(flag.observed_fare)} against a {formatINR(flag.baseline_median_fare)} median across{" "}
                    {flag.baseline_sample_size} earlier real day{flag.baseline_sample_size === 1 ? "" : "s"} —{" "}
                    {flag.pct_above_baseline_median.toFixed(1)}% above.
                  </p>

                  {flag.operator_responded_at && (
                    <p className="text-xs text-ink-muted mb-2">
                      Last filed by {flag.operator_responded_by} on{" "}
                      {new Date(flag.operator_responded_at).toLocaleDateString("en-IN")}.
                    </p>
                  )}

                  <label htmlFor={`response-${flag.id}`} className="text-sm text-ink-secondary">
                    Your account of this fare
                  </label>
                  <textarea
                    id={`response-${flag.id}`}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    rows={4}
                    placeholder="e.g. last remaining fare bucket on a festival-week departure; capacity reduced by an AOG aircraft"
                    className="mt-1 w-full text-sm px-2.5 py-2 rounded-lg border border-border bg-surface text-ink placeholder:text-ink-muted"
                  />
                  <div className="flex flex-wrap gap-2 mt-2">
                    <button
                      disabled={busy || draft.trim().length === 0}
                      onClick={() => submit(flag)}
                      className="text-sm px-3 py-1.5 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors disabled:opacity-50"
                    >
                      {busy ? "Filing…" : "File response"}
                    </button>
                  </div>
                </div>
              );
            })()}
        </div>
      )}
    </Panel>
  );
}
