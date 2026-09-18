import { useState } from "react";
import { api, type CitizenFareReport } from "../api";
import { formatINR } from "../labels";
import { Panel } from "./Panel";

// The regulator's triage queue for public fare reports. Regulator-only, and
// for two separate reasons: a report may carry the reporter's contact email,
// and every one of them is unverified by construction. Publishing them would
// leak the first and let the second be read with the weight of measured data.

export function CitizenReports({
  reports,
  onReviewed,
}: {
  reports: CitizenFareReport[] | null;
  onReviewed: () => void;
}) {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle(report: CitizenFareReport) {
    setError(null);
    if (expandedId === report.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(report.id);
    setNote(report.reviewer_note);
  }

  async function markReviewed(report: CitizenFareReport) {
    setBusy(true);
    setError(null);
    try {
      await api.reviewCitizenReport(report.id, { status: "reviewed", reviewer_note: note });
      setExpandedId(null);
      onReviewed();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="Public fare reports"
      subtitle="Fares reported by members of the public. These are unverified by construction and are deliberately kept separate from the collected fare data — there is no join path between a report and a flag, so an unverified claim can never inherit the credibility of a measured one. Treat them as leads, not evidence."
    >
      {!reports ? (
        <div className="h-12 flex items-center text-sm text-ink-muted">Loading reports…</div>
      ) : reports.length === 0 ? (
        <p className="text-sm text-ink-secondary">No fare reports submitted yet.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {error && (
            <div className="rounded-lg border border-border bg-warning/10 text-ink text-sm px-3 py-2">{error}</div>
          )}
          <div className="scroll-fade-x overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-ink-secondary">
                  <th className="pb-2 pr-3 font-medium">Route as typed</th>
                  <th className="pb-2 pr-3 font-medium">Flying on</th>
                  <th className="pb-2 pr-3 font-medium">Fare claimed</th>
                  <th className="pb-2 pr-3 font-medium">Airline</th>
                  <th className="pb-2 pr-3 font-medium">Submitted</th>
                  <th className="pb-2 pr-3 font-medium">Status</th>
                  <th className="pb-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {reports.map((report) => (
                  <tr key={report.id} className="border-t border-hairline align-top">
                    <td className="py-2 pr-3 whitespace-nowrap font-medium text-ink">
                      {report.origin} → {report.destination}
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap text-ink-secondary">{report.travel_date}</td>
                    <td className="py-2 pr-3 whitespace-nowrap tabular-nums text-ink">
                      {formatINR(report.reported_fare)}
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap text-ink-secondary">
                      {report.carrier_name || "—"}
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap text-ink-muted">
                      {new Date(report.submitted_at).toLocaleDateString("en-IN")}
                    </td>
                    <td className="py-2 pr-3">
                      {report.status === "reviewed" ? (
                        <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-good/15 text-good">
                          Reviewed
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-warning/20 text-ink">
                          New
                        </span>
                      )}
                    </td>
                    <td className="py-2">
                      <button
                        onClick={() => toggle(report)}
                        className="text-xs px-2 py-1 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors whitespace-nowrap"
                      >
                        {expandedId === report.id ? "Close" : "Open"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {expandedId != null &&
            (() => {
              const report = reports.find((r) => r.id === expandedId);
              if (!report) return null;
              return (
                <div className="rounded-xl border border-border p-4 mt-1">
                  <div className="text-sm font-semibold text-ink mb-1">
                    {report.origin} → {report.destination} · {report.travel_date}
                  </div>
                  <p className="text-sm text-ink-secondary">
                    {formatINR(report.reported_fare)} claimed
                    {report.carrier_name ? ` on ${report.carrier_name}` : ""}.
                  </p>

                  {report.note && (
                    <p className="text-sm text-ink mt-2 whitespace-pre-line border-l-2 border-hairline pl-3">
                      {report.note}
                    </p>
                  )}

                  <p className="text-xs text-ink-muted mt-2">
                    {report.contact_email
                      ? `Contact left: ${report.contact_email}`
                      : "No contact details left."}
                  </p>

                  {report.status === "reviewed" ? (
                    <p className="text-sm text-ink-secondary mt-3 border-t border-hairline pt-3">
                      Reviewed{report.reviewer_note ? ` — ${report.reviewer_note}` : "."}
                    </p>
                  ) : (
                    <div className="mt-3 border-t border-hairline pt-3 flex flex-wrap gap-2">
                      <input
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="Triage note (what you did with this)"
                        className="text-sm px-2.5 py-1.5 rounded-lg border border-border bg-surface text-ink placeholder:text-ink-muted flex-1 min-w-[16rem]"
                      />
                      <button
                        disabled={busy}
                        onClick={() => markReviewed(report)}
                        className="text-sm px-3 py-1.5 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors disabled:opacity-50"
                      >
                        {busy ? "Saving…" : "Mark reviewed"}
                      </button>
                    </div>
                  )}
                </div>
              );
            })()}
        </div>
      )}
    </Panel>
  );
}
