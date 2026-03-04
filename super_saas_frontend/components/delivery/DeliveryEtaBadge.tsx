"use client";

import { Badge } from "@/components/ui/badge";
import { useDeliveryEta } from "@/hooks/useDeliveryEta";

interface DeliveryEtaBadgeProps {
  orderId: number;
}

const STATUS_CONFIG = {
  ON_TIME: { label: "No prazo", variant: "success" as const },
  ARRIVING: { label: "Chegando", variant: "warning" as const },
  DELAYED: { label: "Atrasado", variant: "danger" as const },
};

export function DeliveryEtaBadge({ orderId }: DeliveryEtaBadgeProps) {
  const { remainingSeconds, status, loading } = useDeliveryEta(orderId);

  if (loading || remainingSeconds === null || status === null) {
    return null;
  }

  const minutes = Math.ceil(Math.max(remainingSeconds, 0) / 60);
  const statusConfig = STATUS_CONFIG[status];

  return (
    <Badge variant={statusConfig.variant}>
      ⏱ {minutes} min restantes • {statusConfig.label}
    </Badge>
  );
}
