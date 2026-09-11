function Block({ className = "" }: { className?: string }) {
  return <div className={`rounded-2xl border border-border bg-surface animate-pulse ${className}`} />;
}

export function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading dashboard">
      <Block className="h-32" />
      <div className="flex flex-wrap gap-3">
        <Block className="h-20 flex-1 min-w-[200px]" />
        <Block className="h-20 flex-1 min-w-[200px]" />
        <Block className="h-20 flex-1 min-w-[200px]" />
      </div>
      <Block className="h-72" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Block className="h-64" />
        <Block className="h-64" />
      </div>
      <Block className="h-56" />
      <Block className="h-56" />
    </div>
  );
}
