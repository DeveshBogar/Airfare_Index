import type { RouteOut } from "../api";

export function RouteFilter({
  routes,
  value,
  onChange,
}: {
  routes: RouteOut[];
  value: number | null;
  onChange: (routeId: number | null) => void;
}) {
  const sorted = [...routes].sort((a, b) => a.display_name.localeCompare(b.display_name));

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <label htmlFor="route-filter" className="text-sm font-medium text-ink-secondary">
        Route
      </label>
      <select
        id="route-filter"
        value={value ?? "all"}
        onChange={(e) => onChange(e.target.value === "all" ? null : Number(e.target.value))}
        className="text-sm px-3 py-1.5 rounded-lg border border-border bg-surface text-ink cursor-pointer"
      >
        <option value="all">All {routes.length} routes</option>
        {sorted.map((r) => (
          <option key={r.id} value={r.id}>
            {r.display_name}
          </option>
        ))}
      </select>
      <span className="text-xs text-ink-muted">Scopes the charts and table below</span>
    </div>
  );
}
