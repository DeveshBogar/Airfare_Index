// Pure calendar-date helpers shared by any component that needs to
// compute an ISO date relative to "today" - notably DateWatch (tracking
// one exact travel date) and, since it feeds booking-link URLs, anything
// that needs "the date this estimate/aggregate implicitly represents"
// (SectorHeatmap, BookingAdvice: travel_date = today + ap_window_days,
// the same convention the backend's own estimation engine uses).

export function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Pure calendar-date arithmetic, deliberately avoiding any local-midnight ->
// toISOString() round trip: that round trip silently no-ops (or jumps by 2
// days) depending on the browser's UTC offset, since local midnight shifts
// to the previous/next UTC calendar day for many timezones.
export function addDaysISO(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + days);
  return dt.toISOString().slice(0, 10);
}
