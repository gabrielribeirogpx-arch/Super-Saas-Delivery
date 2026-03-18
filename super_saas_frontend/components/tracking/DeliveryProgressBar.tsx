"use client";

import { useMemo } from "react";

type DeliveryProgressBarProps = {
  status: string | null | undefined;
  statusStep?: number | null;
  progress?: number | null;
  distanceKm?: number | null;
  etaSeconds?: number | null;
};

const MAX_STEP = 5;

function formatEta(etaSeconds: number | null | undefined) {
  if (!Number.isFinite(Number(etaSeconds)) || Number(etaSeconds) <= 0) return null;
  const minutes = Math.max(1, Math.round(Number(etaSeconds) / 60));
  return `${minutes} min`;
}

export default function DeliveryProgressBar({ status, statusStep, progress, distanceKm, etaSeconds }: DeliveryProgressBarProps) {
  const safeStep = Math.max(0, Math.min(MAX_STEP, Number(statusStep || 0)));
  const isDelivered = String(status || "").toUpperCase() === "DELIVERED" || safeStep >= MAX_STEP;

  const normalizedProgress = useMemo(() => {
    if (isDelivered) return 1;
    if (Number.isFinite(Number(progress))) return Math.max(0, Math.min(1, Number(progress)));
    if (safeStep <= 0) return 0;
    return (safeStep - 1) / (MAX_STEP - 1);
  }, [isDelivered, progress, safeStep]);

  const formattedEta = formatEta(etaSeconds);
  const formattedDistance = Number.isFinite(Number(distanceKm)) ? `${Number(distanceKm).toFixed(2)} km` : null;

  if (!status && safeStep <= 0) {
    return <div>Carregando rastreamento...</div>;
  }

  return (
    <div className="flex w-full flex-col items-center gap-4">
      <div className="relative h-16 w-full max-w-md">
        <div className="absolute left-0 right-0 top-1/2 h-2 -translate-y-1/2 rounded bg-gray-300" />

        <div
          className="absolute -top-6 text-xl"
          style={{ left: `${normalizedProgress * 100}%`, transform: "translateX(-50%)", transition: "left 0.5s linear" }}
          aria-hidden="true"
        >
          🏍️
        </div>

        <div aria-hidden="true" className="absolute -top-6 right-0 text-xl">
          🏠
        </div>
      </div>

      {isDelivered ? (
        <div className="text-sm font-medium text-green-600">✅ Entregue</div>
      ) : (
        <div className="text-center text-sm text-gray-600">
          <div>Seu pedido está a caminho</div>
          {formattedDistance || formattedEta ? (
            <div className="mt-1 text-xs text-slate-500">
              {[formattedDistance, formattedEta ? `ETA ${formattedEta}` : null].filter(Boolean).join(" • ")}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
