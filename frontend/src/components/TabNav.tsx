import type { ReactNode } from "react";

export type TabKey = "overview" | "trip" | "festivals" | "routes" | "affordability" | "sources";

const TABS: { key: TabKey; label: string; icon: ReactNode }[] = [
  {
    key: "overview",
    label: "Overview",
    icon: (
      <path d="M2.5 13.5v-4M7 13.5v-8M11.5 13.5V4M2.5 13.5h9" strokeLinecap="round" strokeLinejoin="round" />
    ),
  },
  {
    key: "trip",
    label: "Track a Trip",
    icon: (
      <>
        <rect x="2.25" y="3" width="11.5" height="10.5" rx="1.5" strokeLinejoin="round" />
        <path d="M2.25 6h11.5M5 2v2M11 2v2" strokeLinecap="round" />
        <path d="M6 9.5l1.3 1.3L10.5 8" strokeLinecap="round" strokeLinejoin="round" />
      </>
    ),
  },
  {
    key: "festivals",
    label: "Festival Watch",
    icon: (
      <>
        <path d="M8 2.25 9.1 5.2l3.15.28-2.4 2.06.73 3.08L8 8.95l-2.58 1.67.73-3.08-2.4-2.06 3.15-.28z" strokeLinejoin="round" />
      </>
    ),
  },
  {
    key: "routes",
    label: "Explore Routes",
    icon: (
      <>
        <circle cx="3.5" cy="12.5" r="1.5" />
        <circle cx="12.5" cy="3.5" r="1.5" />
        <path d="M3.5 11V8.5A2.5 2.5 0 0 1 6 6h1.5A2.5 2.5 0 0 0 10 3.5V2" strokeLinecap="round" />
      </>
    ),
  },
  {
    key: "affordability",
    label: "Affordability",
    icon: (
      <>
        <path d="M8 2v12M5.5 4.5h3.75a1.75 1.75 0 1 1 0 3.5H6.75a1.75 1.75 0 1 0 0 3.5H10" strokeLinecap="round" strokeLinejoin="round" />
      </>
    ),
  },
  {
    key: "sources",
    label: "Data Sources",
    icon: (
      <>
        <ellipse cx="8" cy="3.4" rx="5" ry="1.8" />
        <path d="M3 3.4v4.6c0 1 2.2 1.8 5 1.8s5-.8 5-1.8V3.4M3 8v4.6c0 1 2.2 1.8 5 1.8s5-.8 5-1.8V8" strokeLinecap="round" />
      </>
    ),
  },
];

export const TAB_KEYS: TabKey[] = TABS.map((t) => t.key);

export function TabNav({ active, onChange }: { active: TabKey; onChange: (t: TabKey) => void }) {
  return (
    <div className="border-b border-border bg-surface">
      <div role="tablist" aria-label="Dashboard sections" className="max-w-[1800px] mx-auto px-6 flex gap-1 overflow-x-auto">
        {TABS.map((t) => {
          const isActive = t.key === active;
          return (
            <button
              key={t.key}
              role="tab"
              aria-selected={isActive}
              aria-controls={`panel-${t.key}`}
              id={`tab-${t.key}`}
              onClick={() => onChange(t.key)}
              className={
                "shrink-0 whitespace-nowrap flex items-center gap-1.5 text-sm font-medium px-3.5 py-2.5 border-b-2 -mb-px transition-colors " +
                (isActive
                  ? "border-series-1 text-ink"
                  : "border-transparent text-ink-secondary hover:text-ink hover:border-hairline")
              }
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.3"
                className={isActive ? "text-series-1" : "text-ink-muted"}
                aria-hidden
              >
                {t.icon}
              </svg>
              {t.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
