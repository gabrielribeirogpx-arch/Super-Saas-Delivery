export const TRACKING_STEPS = [
  { key: "pending", label: "Aguardando cozinha" },
  { key: "preparing", label: "Em preparo" },
  { key: "ready", label: "Pronto" },
  { key: "delivering", label: "Saiu para entrega" },
  { key: "delivered", label: "Entregue" },
] as const;

export const TRACKING_STATUS_STEP: Record<string, number> = {
  pending: 1,
  preparing: 2,
  ready: 3,
  delivering: 4,
  delivered: 5,
  canceled: 1,
};

const TRACKING_STATUS_NORMALIZE: Record<string, string> = {
  // etapa 1
  RECEBIDO: "pending",
  recebido: "pending",
  PENDING: "pending",
  pending: "pending",
  CONFIRMADO: "pending",
  confirmado: "pending",

  // etapa 2
  EM_PREPARO: "preparing",
  em_preparo: "preparing",
  PREPARANDO: "preparing",
  preparando: "preparing",
  PREPARO: "preparing",
  preparo: "preparing",
  PREPARING: "preparing",
  preparing: "preparing",

  // etapa 3
  PRONTO: "ready",
  pronto: "ready",
  READY: "ready",
  ready: "ready",

  // etapa 4
  SAIU_PARA_ENTREGA: "delivering",
  saiu_para_entrega: "delivering",
  EM_ENTREGA: "delivering",
  em_entrega: "delivering",
  DELIVERING: "delivering",
  delivering: "delivering",

  // etapa 5
  ENTREGUE: "delivered",
  entregue: "delivered",
  DELIVERED: "delivered",
  delivered: "delivered",

  // cancelado
  CANCELADO: "canceled",
  cancelado: "canceled",
  CANCELED: "canceled",
  canceled: "canceled",
};

export function normalizeTrackingStatus(raw: string): string {
  const normalizedRaw = String(raw || "").trim();
  if (!normalizedRaw) {
    return "pending";
  }

  return (
    TRACKING_STATUS_NORMALIZE[normalizedRaw] ??
    TRACKING_STATUS_NORMALIZE[normalizedRaw.toUpperCase()] ??
    TRACKING_STATUS_NORMALIZE[normalizedRaw.toLowerCase()] ??
    "pending"
  );
}

export function resolveTrackingStep(status: string, statusStep?: number | null): number {
  const parsedStep = Number(statusStep || 0);
  if (Number.isFinite(parsedStep) && parsedStep > 0) {
    return parsedStep;
  }

  return TRACKING_STATUS_STEP[normalizeTrackingStatus(status)] ?? 1;
}

