import { useState } from "react";
import { getRegulatorToken, setRegulatorToken } from "../regulatorAuth";

// Deliberately not a login form: there is no account, no username, and no
// identity behind this. It's a shared key that unlocks the review actions
// and the draft-notice document, and the wording here says so rather than
// implying an authenticated session.
export function RegulatorTokenGate({ onChange }: { onChange: (token: string | null) => void }) {
  const [draft, setDraft] = useState("");
  const [unlocked, setUnlocked] = useState(getRegulatorToken() != null);

  function unlock() {
    const token = draft.trim();
    if (!token) return;
    setRegulatorToken(token);
    setUnlocked(true);
    setDraft("");
    onChange(token);
  }

  function lock() {
    setRegulatorToken(null);
    setUnlocked(false);
    onChange(null);
  }

  if (unlocked) {
    return (
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium bg-good/15 text-good">
          <span className="h-1.5 w-1.5 rounded-full bg-good" aria-hidden />
          Review actions unlocked
        </span>
        <button
          onClick={lock}
          className="text-sm px-3 py-1.5 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors"
        >
          Lock
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor="regulator-token" className="text-sm text-ink-secondary">
        Access key
      </label>
      <input
        id="regulator-token"
        type="password"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") unlock();
        }}
        placeholder="Shared regulator key"
        className="text-sm px-2.5 py-1.5 rounded-lg border border-border bg-surface text-ink placeholder:text-ink-muted"
      />
      <button
        onClick={unlock}
        disabled={draft.trim().length === 0}
        className="text-sm px-3 py-1.5 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors disabled:opacity-50"
      >
        Unlock
      </button>
    </div>
  );
}
