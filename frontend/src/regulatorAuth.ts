// Holds the shared regulator token for the current browser tab only.
//
// sessionStorage, not localStorage, on purpose: this is a shared secret,
// and it should not survive the tab being closed or sit in storage
// indefinitely on a machine someone else might use next. Losing it on
// close is the correct trade — re-entering it is cheap.
//
// This is not a login. See app/regulator/auth.py: holding the token proves
// possession of a shared key, not identity.

const STORAGE_KEY = "apix_regulator_token";

export function getRegulatorToken(): string | null {
  try {
    const value = sessionStorage.getItem(STORAGE_KEY);
    return value && value.length > 0 ? value : null;
  } catch {
    // Private mode / blocked site data — behave as though unlocked-never.
    return null;
  }
}

export function setRegulatorToken(token: string | null): void {
  try {
    if (token && token.length > 0) {
      sessionStorage.setItem(STORAGE_KEY, token);
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Nothing useful to do — the caller's UI state still reflects intent
    // for this render, it just won't survive a reload.
  }
}
