interface RealtimeBadgeProps {
  label?: string;
}

export function RealtimeBadge({ label = "Realtime" }: RealtimeBadgeProps) {
  return (
    <div className="relative inline-flex items-center gap-2 overflow-hidden rounded-full border border-emerald-200/70 bg-gradient-to-r from-emerald-50/95 via-emerald-100/80 to-lime-100/85 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-800 shadow-[0_10px_24px_-16px_rgba(16,185,129,0.8)] backdrop-blur-sm">
      <span className="pointer-events-none absolute inset-0 bg-gradient-to-r from-white/30 via-transparent to-emerald-200/20" aria-hidden="true" />
      <span className="relative flex h-2.5 w-2.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
      </span>
      <span className="relative">{label}</span>
    </div>
  );
}
