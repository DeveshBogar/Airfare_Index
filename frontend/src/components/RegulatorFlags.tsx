import { useState } from "react";
import { api, RegulatorAuthError, type DraftNotice, type RegulatorFlag, type RegulatorFlagDetail } from "../api";
import { formatINR } from "../labels";
import { DraftNoticeView } from "./DraftNoticeView";
import { FactorList } from "./FactorList";
import { Panel } from "./Panel";

const STATUS_STYLE: Record<string, string> = {
  new: "bg-warning/20 text-ink",
  reviewed: "bg-series-1/15 text-series-1",
  dismissed: "bg-ink-muted/15 text-ink-muted",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap " +
        (STATUS_STYLE[status] ?? "bg-ink-muted/15 text-ink-muted")
      }
    >
      {status}
    </span>
  );
}

export function RegulatorFlags({
  flags,
  loading,
  hasToken,
  onReviewed,
}: {
  flags: RegulatorFlag[] | null;
  loading: boolean;
  hasToken: boolean;
  onReviewed: () => void;
}) {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<RegulatorFlagDetail | null>(null);
  const [notice, setNotice] = useState<DraftNotice | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [busy, setBusy] = useState(false);

  async function toggle(flag: RegulatorFlag) {
    setError(null);
    setNotice(null);
    if (expandedId === flag.id) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(flag.id);
    setDetail(null);
    setNote(flag.review_note);
    setReviewer(flag.reviewed_by);
    try {
      setDetail(await api.regulatorFlag(flag.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function review(flag: RegulatorFlag, status: "reviewed" | "dismissed") {
    setBusy(true);
    setError(null);
    try {
      await api.reviewFlag(flag.id, { status, review_note: note, reviewed_by: reviewer });
      onReviewed();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  async function openNotice(flag: RegulatorFlag) {
    setBusy(true);
    setError(null);
    try {
      setNotice(await api.draftNotice(flag.id));
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="Flagged fares"
      subtitle="Real collected fares that came in both statistically unusual for their own route/carrier/booking-window history AND materially above it. A flag is an observation with its method stated — not a finding of wrongdoing, and not a judgement that any fare was unfair. See docs/regulator_flagging_methodology.md."
    >
      {loading ? (
        <div className="h-16 flex items-center text-sm text-ink-muted">Loading flagged fares…</div>
      ) : !flags || flags.length === 0 ? (
        <p className="text-sm text-ink-secondary">
          No flags yet. Flags appear once a route+carrier+booking-window has enough real daily history for an
          unusual day to stand out against it.
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
                  <th className="pb-2 pr-3 font-medium">Carrier</th>
                  <th className="pb-2 pr-3 font-medium">Window</th>
                  <th className="pb-2 pr-3 font-medium">Observed</th>
                  <th className="pb-2 pr-3 font-medium">Baseline</th>
                  <th className="pb-2 pr-3 font-medium">Above</th>
                  <th className="pb-2 pr-3 font-medium">Seen on</th>
                  <th className="pb-2 pr-3 font-medium">Status</th>
                  <th className="pb-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {flags.map((flag) => (
                  <tr key={flag.id} className="border-t border-hairline align-top">
                    <td className="py-2 pr-3 whitespace-nowrap font-medium text-ink">{flag.route}</td>
                    <td className="py-2 pr-3 whitespace-nowrap text-ink-secondary">{flag.carrier_name}</td>
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
                    <td className="py-2 pr-3">
                      <StatusBadge status={flag.status} />
                    </td>
                    <td className="py-2">
                      <button
                        onClick={() => toggle(flag)}
                        className="text-xs px-2 py-1 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors whitespace-nowrap"
                      >
                        {expandedId === flag.id ? "Hide" : "Examine"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {expandedId != null && (
            <div className="rounded-xl border border-border p-4 mt-1">
              {(() => {
                const flag = flags.find((f) => f.id === expandedId);
                if (!flag) return null;
                return (
                  <>
                    <div className="text-sm font-semibold text-ink mb-1">
                      {flag.route} · {flag.carrier_name} · T+{flag.ap_window_days} · {flag.flagged_search_date}
                    </div>
                    <p className="text-sm text-ink-secondary mb-3">
                      {formatINR(flag.observed_fare)} against a {formatINR(flag.baseline_median_fare)} median across{" "}
                      {flag.baseline_sample_size} earlier real day{flag.baseline_sample_size === 1 ? "" : "s"} —{" "}
                      {flag.pct_above_baseline_median.toFixed(1)}% above, robust z-score{" "}
                      {flag.robust_z_score.toFixed(1)}.
                    </p>

                    <div className="text-xs font-semibold uppercase tracking-wide text-ink-muted mb-1.5">
                      Possible contributing factors (real, dated — not a determination of cause)
                    </div>
                    {detail ? (
                      <FactorList factors={detail.possible_factors} />
                    ) : (
                      <p className="text-sm text-ink-muted">Loading context…</p>
                    )}

                    {hasToken ? (
                      <div className="mt-4 flex flex-col gap-2 border-t border-hairline pt-3">
                        <div className="flex flex-wrap gap-2">
                          <input
                            value={reviewer}
                            onChange={(e) => setReviewer(e.target.value)}
                            placeholder="Your desk / initials"
                            className="text-sm px-2.5 py-1.5 rounded-lg border border-border bg-surface text-ink placeholder:text-ink-muted"
                          />
                          <input
                            value={note}
                            onChange={(e) => setNote(e.target.value)}
                            placeholder="Review note (what you concluded and why)"
                            className="text-sm px-2.5 py-1.5 rounded-lg border border-border bg-surface text-ink placeholder:text-ink-muted flex-1 min-w-[16rem]"
                          />
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <button
                            disabled={busy}
                            onClick={() => review(flag, "reviewed")}
                            className="text-sm px-3 py-1.5 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors disabled:opacity-50"
                          >
                            Mark reviewed
                          </button>
                          <button
                            disabled={busy}
                            onClick={() => review(flag, "dismissed")}
                            className="text-sm px-3 py-1.5 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors disabled:opacity-50"
                          >
                            Dismiss
                          </button>
                          <button
                            disabled={busy}
                            onClick={() => openNotice(flag)}
                            className="text-sm px-3 py-1.5 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors disabled:opacity-50"
                          >
                            Generate draft notice
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-ink-muted mt-4 border-t border-hairline pt-3">
                        Enter the access key above to record a review or generate a draft notice.
                      </p>
                    )}

                    {notice && <DraftNoticeView notice={notice} onClose={() => setNotice(null)} />}
                  </>
                );
              })()}
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

function describeError(e: unknown): string {
  if (e instanceof RegulatorAuthError) {
    return e.status === 503
      ? "The server has no regulator access key configured, so these actions are locked (it fails closed rather than falling open). Set REGULATOR_ACCESS_TOKEN on the backend."
      : "That access key wasn't accepted. Check the key and try again.";
  }
  return e instanceof Error ? e.message : String(e);
}
