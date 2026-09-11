import { useState } from "react";
import { ThemeToggle } from "./ThemeToggle";

export function Header({ onRefresh, refreshing }: { onRefresh: () => void; refreshing: boolean }) {
  const [showAbout, setShowAbout] = useState(false);

  return (
    <header className="bg-surface">
      <div className="max-w-[1800px] mx-auto px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-semibold text-ink tracking-tight">Airfare Price Index</h1>
          <p className="text-sm text-ink-secondary mt-0.5">Tracking real domestic flight prices across India, every day</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setShowAbout((v) => !v)}
            aria-expanded={showAbout}
            className="text-sm px-3 py-1.5 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors"
          >
            How this works
          </button>
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className="text-sm px-3 py-1.5 rounded-lg border border-border text-ink-secondary hover:bg-page hover:text-ink transition-colors disabled:opacity-50"
          >
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
          <ThemeToggle />
        </div>
      </div>

      {showAbout && (
        <div className="border-t border-border bg-page">
          <div className="max-w-[1800px] mx-auto px-6 py-4 text-sm text-ink-secondary leading-relaxed">
            <div className="max-w-5xl grid sm:grid-cols-3 gap-4">
              <div>
                <div className="font-medium text-ink mb-1">What this is</div>
                We check real airline websites every day for actual ticket prices on India's busiest routes, and turn
                those prices into a single index number — the same idea behind the price index used to track
                inflation, applied to flights.
              </div>
              <div>
                <div className="font-medium text-ink mb-1">Where the numbers come from</div>
                Every price shown is a real one we found on an airline's own site. Routes are chosen by how many
                people actually fly them, using government (DGCA) traffic data — not a guess.
              </div>
              <div>
                <div className="font-medium text-ink mb-1">What's still missing</div>
                We only collect from sites that clearly allow it. Several airlines and booking sites don't currently
                permit this, so this index reflects a real but partial slice of the market — see the "Data Sources"
                tab above for exactly which ones and why.
              </div>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
