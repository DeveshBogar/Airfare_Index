import type { CitizenFareReport } from "../api";
import { formatINR } from "../labels";
import { Panel } from "./Panel";

// The other half of what a traveller account is for: having submitted a
// report, you can see whether anyone has actually looked at it. Without an
// account there is nobody to show this to, which is part of why submitting
// requires one.

export function MyReports({ reports }: { reports: CitizenFareReport[] | null }) {
  if (!reports || reports.length === 0) return null;

  return (
    <Panel
      title="Your reports"
      subtitle="Fare reports you submitted, and whether anyone has reviewed them yet. These stay marked unverified throughout — they are not merged into the collected fare data, so an unverified claim never inherits the credibility of a measured one."
    >
      <div className="scroll-fade-x overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-left text-ink-secondary">
              <th className="pb-2 pr-3 font-medium">Route</th>
              <th className="pb-2 pr-3 font-medium">Flying on</th>
              <th className="pb-2 pr-3 font-medium">Fare reported</th>
              <th className="pb-2 pr-3 font-medium">Submitted</th>
              <th className="pb-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((report) => (
              <tr key={report.id} className="border-t border-hairline">
                <td className="py-2 pr-3 whitespace-nowrap font-medium text-ink">
                  {report.origin} → {report.destination}
                </td>
                <td className="py-2 pr-3 whitespace-nowrap text-ink-secondary">{report.travel_date}</td>
                <td className="py-2 pr-3 whitespace-nowrap tabular-nums text-ink">
                  {formatINR(report.reported_fare)}
                </td>
                <td className="py-2 pr-3 whitespace-nowrap text-ink-muted">
                  {new Date(report.submitted_at).toLocaleDateString("en-IN")}
                </td>
                <td className="py-2">
                  {report.status === "reviewed" ? (
                    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-good/15 text-good">
                      Reviewed
                    </span>
                  ) : (
                    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-page text-ink-secondary">
                      Awaiting review
                    </span>
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
