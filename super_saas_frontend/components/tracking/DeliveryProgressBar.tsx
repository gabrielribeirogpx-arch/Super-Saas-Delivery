"use client";

import { useMemo } from "react";

type DeliveryProgressBarProps = {
  status: string | null | undefined;
  statusStep?: number | null;
};

const MAX_STEP = 5;

export default function DeliveryProgressBar({ status, statusStep }: DeliveryProgressBarProps) {
  const safeStep = Math.max(0, Math.min(MAX_STEP, Number(statusStep || 0)));
  const isDelivered = String(status || "").toUpperCase() === "DELIVERED" || safeStep >= MAX_STEP;

  const normalizedProgress = useMemo(() => {
    if (isDelivered) return 1;
    if (safeStep <= 0) return 0;
    return (safeStep - 1) / (MAX_STEP - 1);
  }, [isDelivered, safeStep]);

  if (!status && safeStep <= 0) {
    return <div>Carregando rastreamento...</div>;
  }

  return (
    <div className="flex w-full flex-col items-center gap-4">
      <div className="relative h-16 w-full max-w-md">
        <div className="absolute left-0 right-0 top-1/2 h-2 -translate-y-1/2 rounded bg-gray-300" />

        <div
          className="absolute top-1/2 -translate-y-1/2 transition-all duration-500 ease-in-out"
          style={{ left: `calc(${normalizedProgress * 100}% - 0.5rem)` }}
        >
          <div
            className={`h-4 w-4 rounded-full ${isDelivered ? "bg-green-500" : "bg-emerald-500"}`}
            aria-label={isDelivered ? "Delivery completed" : "Delivery in progress"}
          />
        </div>

        <div aria-hidden="true" className="absolute -top-6 left-0 text-xl">
          🏍️
        </div>
        <div aria-hidden="true" className="absolute -top-6 right-0 text-xl">
          🏠
        </div>
      </div>

      {isDelivered ? (
        <div className="text-sm font-medium text-green-600">✅ Entregue</div>
      ) : (
        <div className="text-sm text-gray-600">Seu pedido está a caminho</div>
      )}
    </div>
  );
}
