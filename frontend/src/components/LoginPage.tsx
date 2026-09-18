import { useState } from "react";
import { api, AuthError } from "../api";
import type { AuthUser } from "../auth";
import { ThemeToggle } from "./ThemeToggle";

// A full page rather than a dropdown in the header, because signing in here
// is a deliberate act with consequences — a government account can record
// review decisions against named carriers, an airline account can file a
// response that a regulator reads. A cramped popover under-sells that.
//
// One form for all three roles: the role lives on the account, so asking
// people to pick "traveller / government / airline" before typing would be
// theatre — the server decides from the account either way, and a wrong
// pick would just be an extra way to fail.

const ROLES: { label: string; blurb: string; accent: string }[] = [
  {
    label: "Travellers",
    blurb:
      "Reading the dashboard needs no account. An account lets you report a fare — reports are tied to a person so the queue can't be flooded anonymously — and follow what happens to it.",
    accent: "bg-good",
  },
  {
    label: "Government officials",
    blurb:
      "The fare-anomaly review queue, public report triage, and draft notice documents. Every decision is recorded against your account.",
    accent: "bg-series-2",
  },
  {
    label: "Airlines",
    blurb:
      "Your own collected fares and your own index against the market, plus the flags raised against you and a written right of reply.",
    accent: "bg-series-3",
  },
];

export function LoginPage({
  onSignedIn,
  onDismiss,
  reason,
}: {
  onSignedIn: (user: AuthUser, token: string) => void;
  onDismiss: () => void;
  /** Set when the user was bounced here by an expired session rather than
   *  arriving on purpose, so the page can say why they're looking at it. */
  reason?: string | null;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!username.trim() || !password) return;
    setBusy(true);
    setError(null);
    try {
      const session = await api.login(username.trim(), password);
      setPassword("");
      onSignedIn(session.user, session.token);
    } catch (e) {
      setError(
        e instanceof AuthError
          ? "Incorrect username or password."
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex justify-end p-4">
        <ThemeToggle />
      </div>

      <main className="flex-1 flex items-center justify-center px-6 pb-16">
        <div className="w-full max-w-4xl grid md:grid-cols-2 gap-8 md:gap-12 items-center">
          <div className="min-w-0">
            <h1 className="text-[26px] font-semibold text-ink tracking-tight">Airfare Price Index</h1>
            <p className="text-sm text-ink-secondary mt-1 leading-relaxed">
              Real domestic airfares across India, collected daily and turned into a price index — the idea
              behind the inflation index, applied to flights.
            </p>
            <p className="text-sm text-ink-secondary mt-3 leading-relaxed">
              Reading any of it needs no account. Signing in is for three things:
            </p>

            <div className="mt-6 flex flex-col gap-4">
              {ROLES.map((role) => (
                <div key={role.label} className="flex gap-3">
                  <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${role.accent}`} aria-hidden />
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-ink">{role.label}</div>
                    <p className="text-sm text-ink-secondary leading-relaxed mt-0.5">{role.blurb}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card-shadow rounded-2xl border border-border bg-surface p-6">
            <h2 className="text-[17px] font-semibold text-ink">Sign in</h2>
            <p className="text-sm text-ink-secondary mt-0.5">
              Accounts are issued by the administrator — there's no public sign-up.
            </p>

            {reason && (
              <div className="mt-4 rounded-lg border border-border bg-warning/10 text-ink text-sm px-3 py-2">
                {reason}
              </div>
            )}

            <form onSubmit={submit} className="mt-5 flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="login-username" className="text-sm font-medium text-ink">
                  Username
                </label>
                <input
                  id="login-username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  autoFocus
                  autoCapitalize="none"
                  spellCheck={false}
                  className="text-sm px-3 py-2 rounded-lg border border-border bg-page text-ink placeholder:text-ink-muted"
                  placeholder="e.g. traveller"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="login-password" className="text-sm font-medium text-ink">
                  Password
                </label>
                <input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  className="text-sm px-3 py-2 rounded-lg border border-border bg-page text-ink placeholder:text-ink-muted"
                  placeholder="••••••••"
                />
              </div>

              {error && (
                <div
                  role="alert"
                  className="rounded-lg border border-critical/30 bg-critical/10 text-ink text-sm px-3 py-2"
                >
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={busy || !username.trim() || !password}
                className="mt-1 text-sm font-medium px-3 py-2.5 rounded-lg bg-series-1 text-white hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {busy ? "Signing in…" : "Sign in"}
              </button>
            </form>

            <div className="mt-5 pt-4 border-t border-hairline">
              <button
                onClick={onDismiss}
                className="text-sm text-ink-secondary hover:text-ink transition-colors"
              >
                ← Continue without signing in
              </button>
              <p className="text-xs text-ink-muted mt-1.5 leading-relaxed">
                The index, route explorer, festival watch, affordability data and data sources are open to
                everyone. Only submitting a fare report needs a traveller account.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
