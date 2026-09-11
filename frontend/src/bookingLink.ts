// Builds a "check this price" link for a fare shown anywhere on the site.
//
// SpiceJet is the ONLY source whose results page takes a plain,
// documented query string — the exact URL our own scraper already uses
// (see backend/app/scraper/sources/spicejet.py) and has validated works
// against the live site. So a real, single-quote, single-carrier
// SpiceJet fare with a known travel date goes straight to SpiceJet's own
// live results for that route and date — as close to "the official
// booking page for that flight" as is honestly possible.
//
// Every other case falls back to Google Flights:
//   - Akasa (carrier "QP") has no query-string shortcut at all — its
//     booking widget is a client-rendered React form the scraper has to
//     drive by clicking/typing (see akasa.py) — so there is no reliable
//     deep link to build for it.
//   - Any aggregated or blended-carrier number (a heatmap cell, a
//     festival-window price, a "typical fare", a booking-window mean)
//     isn't honestly attributable to one airline at all.
//   - Every estimated price is, by definition, not a real quote to link
//     to — Google Flights with the same route/date the estimate was
//     computed for surfaces the closest real, current results instead.
// Google Flights' plain-language query param reliably prefills origin,
// destination and date from IATA codes without needing a booking API or
// partnership, and shows real current multi-airline results — including
// SpiceJet's and Akasa's own fares.
//
// This never claims to reproduce the exact displayed price — real fares
// change constantly and estimates were never a specific bookable fare in
// the first place. Every caller should make that honest framing visible
// next to the link (see the "Check current price" legend pattern used
// alongside these links).

import type { RouteOut } from "./api";

export interface BookingLinkInfo {
  url: string;
  label: string;
}

/**
 * Several API responses (fares, the heatmap, festival prices, affordability)
 * carry only a route's display name ("Delhi-Patna"), not its origin/
 * destination IATA codes needed to build a link — while /api/routes
 * already returns both. This indexes that list once by display name so
 * callers can resolve either from whichever one they have on hand.
 */
export function buildRouteLookup(routes: RouteOut[]): Record<string, RouteOut> {
  const map: Record<string, RouteOut> = {};
  for (const r of routes) map[r.display_name] = r;
  return map;
}

export function bookingLinkFor(params: {
  origin: string;
  destination: string;
  travelDate?: string | null; // ISO yyyy-mm-dd
  carrierCode?: string | null;
}): BookingLinkInfo {
  const { origin, destination, travelDate, carrierCode } = params;

  if (carrierCode === "SG" && travelDate) {
    const url =
      "https://www.spicejet.com/search" +
      `?from=${origin}&to=${destination}&tripType=1&departure=${travelDate}` +
      "&adult=1&child=0&srCitizen=0&infant=0&currency=INR&redirectTo=/";
    return { url, label: "Check on SpiceJet" };
  }

  // "one-way" is explicit because every fare this app shows is one-way
  // (the scraper only ever searches one-way trips) - without it Google
  // Flights defaults to round-trip, showing a different, inflated price.
  const query = travelDate
    ? `One-way flights to ${destination} from ${origin} on ${travelDate}`
    : `One-way flights to ${destination} from ${origin}`;
  return {
    url: `https://www.google.com/travel/flights?q=${encodeURIComponent(query)}`,
    label: "Check current prices",
  };
}
