interface ActiveDriverInfo {
  name: string;
  status: string;
  updatedAt: string;
  eta?: string;
}

interface FloatingDriverCardProps {
  driver: ActiveDriverInfo | null;
}

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

export function FloatingDriverCard({ driver }: FloatingDriverCardProps) {
  if (!driver) return null;

  return (
    <div className="pointer-events-none absolute bottom-4 left-4 w-[280px] rounded-2xl border border-white/50 bg-white/95 p-3.5 shadow-[0_10px_30px_rgba(0,0,0,0.15)] backdrop-blur-xl">
      <div className="text-xs text-slate-500">Entregador</div>
      <div className="truncate text-sm font-semibold text-slate-900">{driver.name}</div>
      <div className="mt-2 text-xs text-slate-500">Status</div>
      <div className="text-sm font-medium text-slate-800">{driver.status}</div>
      <div className="mt-2 text-xs text-slate-500">Última atualização</div>
      <div className="text-sm text-slate-800">{formatTime(driver.updatedAt)}</div>
      <div className="mt-2 text-xs text-slate-500">ETA</div>
      <div className="text-sm text-slate-800">{driver.eta ?? "--"}</div>
    </div>
  );
}
