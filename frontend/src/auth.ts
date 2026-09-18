// Session token storage for the three role logins.
//
// sessionStorage rather than localStorage, deliberately. A token here is a
// bearer credential for a named account — including, for a regulator login,
// the ability to record review decisions against real carriers. Keeping it
// out of long-lived storage means it does not sit on a shared machine after
// the tab is closed, and it narrows the window in which any future XSS bug
// could lift a still-valid token. The cost is signing in again after
// closing the tab, which is the right trade for what this unlocks.
//
// The token is opaque to the frontend: its role claim is signed, but the
// backend re-reads the account on every request and decides from the
// database (see app/auth/deps.py). Nothing here is an access decision — the
// role below only chooses which tabs to render.

// A traveller signs in only to *submit* a fare report and follow it —
// reading the dashboard never needs an account.
export type Role = "citizen" | "regulator" | "operator";

export interface AuthUser {
  id: number;
  username: string;
  role: Role;
  role_label: string;
  display_name: string;
  organisation: string;
  carrier_code: string | null;
  carrier_name: string | null;
  last_login_at: string | null;
}

const STORAGE_KEY = "apix_session_token";

export function getToken(): string | null {
  try {
    const value = sessionStorage.getItem(STORAGE_KEY);
    return value && value.length > 0 ? value : null;
  } catch {
    // Private mode or blocked site data — behave as signed out.
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token && token.length > 0) {
      sessionStorage.setItem(STORAGE_KEY, token);
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Nothing useful to do — the caller's own state still reflects intent
    // for this session, it just won't survive a reload.
  }
}

/** Where a role lands when it signs in, so each one arrives at the thing its
 *  account actually unlocks. */
export function landingTabFor(role: Role): string {
  if (role === "operator") return "airline";
  if (role === "regulator") return "regulator";
  return "report";
}
