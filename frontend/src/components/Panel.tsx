import { useState, type ReactNode } from "react";

export function Panel({
  title,
  subtitle,
  children,
  right,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  right?: ReactNode;
}) {
  const [showInfo, setShowInfo] = useState(false);

  return (
    <section className="card-shadow min-w-0 rounded-2xl border border-border bg-surface p-5">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
            {subtitle && (
              <button
                type="button"
                onClick={() => setShowInfo((v) => !v)}
                aria-expanded={showInfo}
                aria-label={showInfo ? "Hide description" : "What is this?"}
                title={showInfo ? "Hide description" : "What is this?"}
                className={
                  "shrink-0 h-4 w-4 rounded-full text-[10px] font-bold leading-none flex items-center justify-center border transition-colors cursor-pointer " +
                  (showInfo
                    ? "border-series-1 bg-series-1 text-white"
                    : "border-ink-muted/50 text-ink-muted hover:border-ink-muted hover:text-ink")
                }
              >
                ?
              </button>
            )}
          </div>
          {subtitle && showInfo && (
            <p className="text-sm text-ink-secondary mt-1.5 max-w-2xl leading-relaxed">{subtitle}</p>
          )}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}
