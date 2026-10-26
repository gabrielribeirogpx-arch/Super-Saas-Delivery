interface MapHeaderProps {
  followMode: boolean;
  onToggleFollowMode: () => void;
}

export function MapHeader({ followMode, onToggleFollowMode }: MapHeaderProps) {
  return (
    <div className="rounded-[20px] border border-slate-100 bg-white px-5 py-4 shadow-[0_15px_40px_rgba(0,0,0,0.08),0_5px_12px_rgba(0,0,0,0.05)]">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-slate-900">Fleet Live Map</h1>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-3.5 py-1.5 text-xs font-semibold text-green-600">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-500 opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-green-500" />
            </span>
            REALTIME
          </span>
        </div>

        <button
          type="button"
          className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 transition hover:border-slate-400 hover:text-slate-900"
          onClick={onToggleFollowMode}
        >
          Follow Mode: {followMode ? "ON" : "OFF"}
        </button>
      </div>
    </div>
  );
}
