import type { ComplianceStatus } from "../api";
import { plainComplianceReason } from "../labels";
import { Panel } from "./Panel";

function StatusBadge({ allowed }: { allowed: boolean | null }) {
  if (allowed === true) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium bg-good/15 text-good">
        <span className="h-1.5 w-1.5 rounded-full bg-good" aria-hidden />
        Collecting now
      </span>
    );
  }
  if (allowed === false) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium bg-warning/20 text-ink">
        <span className="h-1.5 w-1.5 rounded-full bg-warning" aria-hidden />
        Not available
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium bg-ink-muted/15 text-ink-muted">
      <span className="h-1.5 w-1.5 rounded-full bg-ink-muted" aria-hidden />
      Not checked yet
    </span>
  );
}

export function DataSources({ rows }: { rows: ComplianceStatus[] }) {
  const sorted = [...rows].sort((a, b) => Number(b.allowed) - Number(a.allowed));

  return (
    <Panel
      title="Where this data comes from"
      subtitle="We only collect prices from a site if its own rules (robots.txt) clearly allow it — checked automatically, every time we run, not assumed once and forgotten."
    >
      <div className="scroll-fade-x overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-ink-secondary">
              <th className="pb-2 pr-3 font-medium">Site</th>
              <th className="pb-2 pr-3 font-medium">Type</th>
              <th className="pb-2 pr-3 font-medium">Status</th>
              <th className="pb-2 font-medium">Why</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.source_id} className="border-t border-hairline">
                <td className="py-2 pr-3 font-medium whitespace-nowrap text-ink">{r.name}</td>
                <td className="py-2 pr-3 whitespace-nowrap capitalize text-ink-secondary">
                  {r.kind === "ota" ? "Booking site" : "Airline"}
                </td>
                <td className="py-2 pr-3 whitespace-nowrap">
                  <StatusBadge allowed={r.allowed} />
                </td>
                <td className="py-2 text-ink-secondary max-w-[420px]">
                  {plainComplianceReason(r.allowed, r.reason)}
                  {r.reason && (
                    <details className="inline">
                      <summary className="inline cursor-pointer text-ink-muted text-xs ml-1">details</summary>
                      <div className="text-xs text-ink-muted mt-1">{r.reason}</div>
                    </details>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
