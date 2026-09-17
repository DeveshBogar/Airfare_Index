import type { DraftNotice, PossibleFactor } from "../api";
import { formatINR } from "../labels";
import { FactorList } from "./FactorList";

// Renders the draft document and nothing else. There is no "send" control
// here and there must never be one — see app/regulator/notice_draft.py:
// this project has no authority to issue anything to an airline. A human
// reads this, decides, and acts through their own official channels.
export function DraftNoticeView({ notice, onClose }: { notice: DraftNotice; onClose: () => void }) {
  const subject = notice.subject as Record<string, string | number>;
  const obs = notice.observation as Record<string, number | string | null>;

  return (
    <div className="mt-3 rounded-xl border border-border bg-surface-raised">
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-hairline print:hidden">
        <span className="text-sm font-medium text-ink">Draft notice — flag #{notice.flag_id}</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.print()}
            className="text-sm px-3 py-1.5 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors"
          >
            Print / save as PDF
          </button>
          <button
            onClick={onClose}
            className="text-sm px-3 py-1.5 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors"
          >
            Close
          </button>
        </div>
      </div>

      <div className="draft-notice-printable px-4 py-4 flex flex-col gap-4">
        {/* The disclaimer leads, and is styled to be the first thing read —
            this document could be forwarded out of context. */}
        <div className="rounded-lg bg-warning/15 border border-warning/40 px-3 py-2.5 text-sm text-ink font-medium leading-relaxed">
          {notice.draft_disclaimer}
        </div>

        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-ink-muted mb-1.5">Subject</div>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-sm">
            <Row label="Carrier" value={`${subject.carrier_name} (${subject.carrier_code})`} />
            <Row label="Route" value={String(subject.route)} />
            <Row label="Booking window" value={`T+${subject.ap_window_days} days`} />
            <Row label="Fare observed on" value={String(subject.observed_on)} />
            <Row label="Travel date priced" value={String(subject.travel_date_priced)} />
          </dl>
        </div>

        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-ink-muted mb-1.5">Observation</div>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-sm">
            <Row label="Observed fare" value={formatINR(Number(obs.observed_fare_inr))} />
            <Row label="Baseline median" value={formatINR(Number(obs.baseline_median_fare_inr))} />
            <Row label="Above baseline" value={`+${Number(obs.pct_above_baseline_median).toFixed(1)}%`} />
            <Row label="Robust z-score" value={Number(obs.robust_z_score).toFixed(1)} />
            <Row label="Baseline MAD" value={formatINR(Number(obs.baseline_mad))} />
            <Row label="Baseline sample" value={`${obs.baseline_sample_size} real prior days`} />
          </dl>
        </div>

        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-ink-muted mb-1.5">Method</div>
          <p className="text-sm text-ink-secondary leading-relaxed">{notice.detection_method_note}</p>
        </div>

        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-ink-muted mb-1.5">
            Possible contributing factors (real, dated — not a determination of cause)
          </div>
          <FactorList factors={notice.possible_factors as PossibleFactor[]} />
        </div>

        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-ink-muted mb-1.5">Review status</div>
          <p className="text-sm text-ink-secondary">
            {notice.regulator_review.status}
            {notice.regulator_review.reviewed_by ? ` — ${notice.regulator_review.reviewed_by}` : ""}
            {notice.regulator_review.reviewed_at ? ` (${notice.regulator_review.reviewed_at})` : ""}
            {notice.regulator_review.review_note ? `: ${notice.regulator_review.review_note}` : ""}
          </p>
        </div>

        <div className="rounded-lg border border-border bg-page px-3 py-2.5 text-sm text-ink-secondary leading-relaxed">
          {notice.boundary_notice}
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-hairline py-1">
      <dt className="text-ink-secondary">{label}</dt>
      <dd className="text-ink font-medium text-right">{value}</dd>
    </div>
  );
}
