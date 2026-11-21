"use client";

import { Clock3 } from "lucide-react";
import { useDeliveryEta } from "@/hooks/useDeliveryEta";

interface DeliveryEtaBadgeProps {
  orderId: number;
}

const STATUS_CONFIG = {
  ON_TIME: { label: "No prazo", className: "border-emerald-100 bg-emerald-50 text-emerald-800" },
  ARRIVING: { label: "Chegando", className: "border-red-100 bg-red-50 text-red-700" },
  DELAYED: { label: "Atrasado", className: "border-amber-100 bg-amber-50 text-amber-800" },
};

export function DeliveryEtaBadge({ orderId }: DeliveryEtaBadgeProps) {
  const { remainingSeconds, status, loading } = useDeliveryEta(orderId);

  if (loading || remainingSeconds === null || status === null) {
    return null;
  }

  const minutes = Math.ceil(Math.max(remainingSeconds, 0) / 60);
  const statusConfig = STATUS_CONFIG[status];

  return (
    <div className={`flex min-w-0 items-center gap-2.5 rounded-xl border px-3 py-2.5 ${statusConfig.className}`} aria-live="polite">
      <Clock3 className="h-4 w-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-bold uppercase tracking-wider opacity-75">Previsão</p>
        <p className="text-sm font-bold leading-5">{status === "DELAYED" ? "Prazo estimado excedido" : `Chegada em cerca de ${minutes} min`}</p>
      </div>
      <span className="shrink-0 rounded-full bg-white/75 px-2 py-1 text-[10px] font-bold">{statusConfig.label}</span>
    </div>
  );
}
