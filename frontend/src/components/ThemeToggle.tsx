import { useEffect, useState, type ReactNode } from "react";
import { applyTheme, getStoredTheme, type ThemePref } from "../theme";

const OPTIONS: { value: ThemePref; label: string; icon: ReactNode }[] = [
  {
    value: "light",
    label: "Light theme",
    icon: (
      <>
        <circle cx="8" cy="8" r="3.25" />
        <path d="M8 1.5v1.5M8 13v1.5M14.5 8H13M3 8H1.5M12.36 3.64l-1.06 1.06M4.7 11.3l-1.06 1.06M12.36 12.36l-1.06-1.06M4.7 4.7 3.64 3.64" strokeLinecap="round" />
      </>
    ),
  },
  {
    value: "dark",
    label: "Dark theme",
    icon: <path d="M13.5 9.7A5.8 5.8 0 0 1 6.3 2.5a5.8 5.8 0 1 0 7.2 7.2Z" strokeLinejoin="round" />,
  },
  {
    value: "system",
    label: "Match system",
    icon: (
      <>
        <rect x="1.75" y="2.75" width="12.5" height="8.5" rx="1.25" strokeLinejoin="round" />
        <path d="M5.5 13.75h5M8 11.25v2.5" strokeLinecap="round" />
      </>
    ),
  },
];

export function ThemeToggle() {
  const [theme, setTheme] = useState<ThemePref>(() => getStoredTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  return (
    <div role="radiogroup" aria-label="Color theme" className="inline-flex items-center gap-0.5 rounded-lg border border-border p-0.5">
      {OPTIONS.map((opt) => {
        const isActive = theme === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={isActive}
            title={opt.label}
            onClick={() => setTheme(opt.value)}
            className={
              "flex items-center justify-center h-7 w-7 rounded-md transition-colors " +
              (isActive ? "bg-page text-ink" : "text-ink-muted hover:text-ink")
            }
          >
            <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden>
              {opt.icon}
            </svg>
            <span className="sr-only">{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
