import { useState } from "react";
import { api, type CitizenReportCount } from "../api";
import { Panel } from "./Panel";

// Intake for the travelling public. Reading this page needs no account;
// submitting does, because an open write endpoint feeding a human triage
// queue is an invitation to flood it.
//
// These reports are stored entirely separately from the system's own
// real-data flags and are never merged into them — an unverified claim must
// not inherit the credibility of collected data. The copy below says that
// plainly to the person submitting, so nobody is misled about what happens
// next.
export function CitizenReportForm({
  count,
  signedIn,
  onRequestSignIn,
  onSubmitted,
}: {
  count: CitizenReportCount | null;
  signedIn: boolean;
  onRequestSignIn: () => void;
  onSubmitted: () => void;
}) {
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [travelDate, setTravelDate] = useState("");
  const [fare, setFare] = useState("");
  const [carrier, setCarrier] = useState("");
  const [note, setNote] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const canSubmit =
    origin.trim().length > 0 && destination.trim().length > 0 && travelDate.length > 0 && Number(fare) > 0;

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api.submitCitizenReport({
        origin: origin.trim(),
        destination: destination.trim(),
        travel_date: travelDate,
        reported_fare: Number(fare),
        carrier_name: carrier.trim(),
        note: note.trim(),
        contact_email: email.trim(),
      });
      setDone(true);
      setOrigin("");
      setDestination("");
      setTravelDate("");
      setFare("");
      setCarrier("");
      setNote("");
      setEmail("");
      onSubmitted();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="Report a fare you think is unreasonable"
      subtitle="Submissions are unverified by definition — they are stored separately from this system's own collected price data and are never mixed into the flagged-fares list. A reviewer can read them alongside the real data, but a report on its own is not evidence of anything. Reporting needs an account so the queue can't be flooded anonymously; reading anything else on this site does not."
    >
      <div className="flex flex-col gap-3">
        {count && (
          <p className="text-sm text-ink-secondary">
            {count.total} report{count.total === 1 ? "" : "s"} submitted so far · {count.new} awaiting review
          </p>
        )}

        {!signedIn && (
          <div className="rounded-xl border border-border bg-page p-4">
            <p className="text-sm text-ink">Sign in to report a fare.</p>
            <p className="text-sm text-ink-secondary mt-1 leading-relaxed max-w-2xl">
              Every report goes into a queue a person reads, so each one is tied to an account — that way a
              flood of junk is traceable and removable, instead of drowning the real reports. Everything else
              on this dashboard stays open without signing in.
            </p>
            <button
              onClick={onRequestSignIn}
              className="mt-3 text-sm px-3 py-1.5 rounded-lg border border-border text-ink-secondary hover:bg-surface hover:text-ink transition-colors"
            >
              Sign in
            </button>
          </div>
        )}

        {/* The form is hidden rather than disabled when signed out: a greyed-out
            set of fields invites someone to fill it in and only then discover
            they can't send it. */}
        {signedIn && (
        <>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          <Field label="From" value={origin} onChange={setOrigin} placeholder="Delhi" />
          <Field label="To" value={destination} onChange={setDestination} placeholder="Patna" />
          <div className="flex flex-col gap-1">
            <label className="text-xs text-ink-secondary" htmlFor="cr-date">
              Travel date
            </label>
            <input
              id="cr-date"
              type="date"
              value={travelDate}
              onChange={(e) => setTravelDate(e.target.value)}
              className="text-sm px-2.5 py-1.5 rounded-lg border border-border bg-surface text-ink"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-ink-secondary" htmlFor="cr-fare">
              Fare you saw (₹)
            </label>
            <input
              id="cr-fare"
              type="number"
              min="0"
              value={fare}
              onChange={(e) => setFare(e.target.value)}
              placeholder="24000"
              className="text-sm px-2.5 py-1.5 rounded-lg border border-border bg-surface text-ink placeholder:text-ink-muted"
            />
          </div>
          <Field label="Airline (optional)" value={carrier} onChange={setCarrier} placeholder="SpiceJet" />
          <div className="flex flex-col gap-1 sm:col-span-2">
            <label className="text-xs text-ink-secondary" htmlFor="cr-note">
              What seemed wrong (optional)
            </label>
            <input
              id="cr-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Doubled overnight for the same flight"
              className="text-sm px-2.5 py-1.5 rounded-lg border border-border bg-surface text-ink placeholder:text-ink-muted"
            />
          </div>
          <Field
            label="Email (optional)"
            value={email}
            onChange={setEmail}
            placeholder="only if you want a reply"
          />
        </div>

        <p className="text-xs text-ink-muted">
          Email is optional and only used if a reviewer needs to follow up. Please don't include any other personal
          details — nothing else is asked for and nothing else should be submitted.
        </p>

        {error && (
          <div className="rounded-lg border border-border bg-warning/10 text-ink text-sm px-3 py-2">{error}</div>
        )}
        {done && !error && (
          <div className="rounded-lg bg-good/10 text-ink text-sm px-3 py-2">
            Report submitted. It will sit in the review queue as an unverified report — thank you.
          </div>
        )}

        <div>
          <button
            onClick={submit}
            disabled={!canSubmit || busy}
            className="text-sm px-3.5 py-2 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors disabled:opacity-50"
          >
            {busy ? "Submitting…" : "Submit report"}
          </button>
        </div>
        </>
        )}
      </div>
    </Panel>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  const id = `cr-${label.toLowerCase().replace(/[^a-z]+/g, "-")}`;
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-ink-secondary" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="text-sm px-2.5 py-1.5 rounded-lg border border-border bg-surface text-ink placeholder:text-ink-muted"
      />
    </div>
  );
}
