import type { CSSProperties, ReactNode } from "react";

/**
 * Wraps a displayed price as a link to check/book it — see
 * ../bookingLink.ts for how the target URL and label are chosen, and why
 * it's never guaranteed to reproduce the exact price shown. Renders a
 * plain <span> (same className/style, just no href) whenever `href` is
 * null, which happens for prices with genuinely nothing to link to (a
 * sold-out checkpoint, a missing fare, a route we can't resolve) — so a
 * caller passing box styling (e.g. a colored heatmap cell) keeps looking
 * right either way, and every call site can stay uniform rather than
 * branching itself.
 */
export function PriceLink({
  href,
  label,
  children,
  className = "",
  style,
}: {
  href: string | null;
  label: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  if (!href) {
    return (
      <span className={className} style={style}>
        {children}
      </span>
    );
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      title={`${label} ↗ — opens in a new tab. Prices change constantly, so this may differ from what's shown here.`}
      className={`cursor-pointer underline decoration-dotted decoration-ink-muted/50 underline-offset-2 hover:decoration-ink hover:text-series-1 transition-colors ${className}`}
      style={style}
    >
      {children}
    </a>
  );
}
