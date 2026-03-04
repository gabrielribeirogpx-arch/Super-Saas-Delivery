interface RealtimeBadgeProps {
  label?: string;
}

export function RealtimeBadge({ label = "Realtime" }: RealtimeBadgeProps) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50/90 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-700 shadow-sm">
      <span className="relative flex h-2.5 w-2.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
      </span>
      {label}
    </div>
  );
}
