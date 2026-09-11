export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="card-shadow rounded-2xl border border-border bg-surface p-8 flex flex-col items-center text-center gap-3">
      <div className="h-10 w-10 rounded-full bg-critical/12 flex items-center justify-center" aria-hidden>
        <svg width="20" height="20" viewBox="0 0 16 16" fill="none" stroke="var(--color-critical)" strokeWidth="1.4">
          <circle cx="8" cy="8" r="6.25" />
          <path d="M8 5.25v3.25" strokeLinecap="round" />
          <circle cx="8" cy="10.75" r="0.4" fill="var(--color-critical)" stroke="none" />
        </svg>
      </div>
      <div className="font-medium text-ink">Couldn't load the dashboard</div>
      <p className="text-sm text-ink-secondary max-w-md leading-relaxed">
        The API isn't responding ({message}). If you're running this locally, make sure the backend server is
        started.
      </p>
      <button
        onClick={onRetry}
        className="text-sm px-4 py-1.5 rounded-lg border border-border text-ink hover:bg-page transition-colors"
      >
        Try again
      </button>
    </div>
  );
}
