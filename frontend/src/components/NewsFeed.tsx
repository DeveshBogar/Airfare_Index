import type { News, NewsItem } from "../api";
import { NEWS_CATEGORY_LABEL } from "../labels";
import { Panel } from "./Panel";

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const diffMin = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60_000));
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${Math.round(diffHr / 24)}d ago`;
}

function NewsRow({ item }: { item: NewsItem }) {
  return (
    <li className="py-3 first:pt-0 last:pb-0 border-b border-hairline last:border-b-0">
      <div className="flex flex-wrap items-center gap-1.5 mb-1">
        {item.categories.map((c) => (
          <span
            key={c}
            className="inline-flex items-center rounded-full bg-series-1/10 text-series-1 px-2 py-0.5 text-[11px] font-medium"
          >
            {NEWS_CATEGORY_LABEL[c] ?? c}
          </span>
        ))}
      </div>
      <a
        href={item.link}
        target="_blank"
        rel="noreferrer"
        className="text-[14px] font-medium text-ink leading-snug hover:underline"
      >
        {item.title}
      </a>
      {item.summary && <p className="text-sm text-ink-secondary mt-1 leading-relaxed">{item.summary}</p>}
      <div className="text-xs text-ink-muted mt-1">
        {item.source}
        {item.published_at && <> · {timeAgo(item.published_at)}</>}
      </div>
    </li>
  );
}

export function NewsFeed({ news, loading }: { news: News | null; loading: boolean }) {
  return (
    <Panel
      title="What's moving airfares in the news"
      subtitle="Real headlines from named publishers (see the source list below), kept only when they mention something that actually drives fares — fuel cost, regulation, airline capacity, travel demand, or disruption. This never claims a headline caused a specific move in the index above; it's real-world context to weigh alongside the real trend, not a prediction."
    >
      {loading ? (
        <div className="h-16 flex items-center text-sm text-ink-muted">Checking the news…</div>
      ) : !news || news.items.length === 0 ? (
        <p className="text-sm text-ink-secondary">
          No airfare-relevant headlines turned up in the latest check — could be a quiet news day, or a source
          couldn't be reached just now.
        </p>
      ) : (
        <ul>
          {news.items.map((item) => (
            <NewsRow key={item.link} item={item} />
          ))}
        </ul>
      )}
      {news && (
        <p className="text-xs text-ink-muted mt-4">
          Sources checked:{" "}
          {news.sources_checked.map((s, i) => (
            <span key={s.name}>
              {i > 0 && ", "}
              <span title={s.reason} className={s.allowed ? undefined : "line-through decoration-ink-muted/60"}>
                {s.name}
              </span>
            </span>
          ))}{" "}
          · as of {new Date(news.as_of).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
        </p>
      )}
    </Panel>
  );
}
