// Plain-language labels shared across components — one place to keep the
// "how far ahead was this booked" phrasing and technical-reason
// translations consistent everywhere they appear.

export const AP_WINDOW_SHORT: Record<number, string> = {
  1: "1 day",
  7: "1 wk",
  15: "2 wks",
  30: "1 mo",
  45: "6 wks",
};

export const AP_WINDOW_FULL: Record<number, string> = {
  1: "Booked 1 day ahead",
  7: "Booked 1 week ahead",
  15: "Booked 2 weeks ahead",
  30: "Booked 1 month ahead",
  45: "Booked 6 weeks ahead",
};

export function apWindowShort(days: number): string {
  return AP_WINDOW_SHORT[days] ?? `${days}d`;
}

export function apWindowFull(days: number): string {
  return AP_WINDOW_FULL[days] ?? `Booked ${days} days ahead`;
}

export function formatINR(value: number): string {
  return `₹${Math.round(value).toLocaleString("en-IN")}`;
}

// Translates the compliance gate's technical robots.txt reasoning into a
// one-line plain-English explanation. The full technical string stays
// available for anyone who wants it (see DataSources.tsx).
export function plainComplianceReason(allowed: boolean | null, reason: string | null): string {
  if (allowed === null) return "Haven't checked this site's rules yet.";
  if (allowed) return "This site's rules allow automatic price-checking.";
  const r = (reason ?? "").toLowerCase();
  if (r.includes("unreachable")) return "This site blocks automated visits outright — we can't even confirm its rules.";
  if (r.includes("disallow")) return "This site's own rules (robots.txt) say not to.";
  return "This site doesn't currently allow automatic price-checking.";
}
