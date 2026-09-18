import type { AuthUser } from "../auth";

// The header's account corner: who you are and a way out, or a way in.
// The sign-in form itself lives on its own page (LoginPage) rather than in
// a popover here — see that file for why.

const ROLE_ACCENT: Record<string, string> = {
  regulator: "bg-series-2/15 text-series-2",
  operator: "bg-series-3/15 text-series-3",
  citizen: "bg-good/15 text-good",
};

export function AccountControl({
  user,
  onRequestSignIn,
  onSignOut,
}: {
  user: AuthUser | null;
  onRequestSignIn: () => void;
  onSignOut: () => void;
}) {
  if (!user) {
    return (
      <button
        onClick={onRequestSignIn}
        className="text-sm px-3 py-1.5 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors"
      >
        Sign in
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span
        className={
          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium " +
          (ROLE_ACCENT[user.role] ?? "bg-good/15 text-good")
        }
        title={user.organisation || undefined}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
        {user.role_label}
        {user.carrier_name ? ` · ${user.carrier_name}` : ""}
      </span>
      <span className="text-sm text-ink-secondary hidden md:inline">
        {user.display_name || user.username}
      </span>
      <button
        onClick={onSignOut}
        className="text-sm px-3 py-1.5 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors"
      >
        Sign out
      </button>
    </div>
  );
}
