"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

interface DeliveryEtaBadgeProps {
  orderId: number;
}

type EtaStatus = "ON_TIME" | "ARRIVING" | "DELAYED";

interface EtaResponse {
  remaining_seconds: number;
  status: EtaStatus;
}

const ETA_CACHE_TTL_MS = 25_000;
const etaCache = new Map<number, { data: EtaResponse; updatedAt: number }>();
const etaInFlight = new Map<number, Promise<EtaResponse>>();

async function fetchOrderEta(orderId: number, force = false): Promise<EtaResponse> {
  const cached = etaCache.get(orderId);
  const now = Date.now();

  if (!force && cached && now - cached.updatedAt < ETA_CACHE_TTL_MS) {
    return cached.data;
  }

  const currentRequest = etaInFlight.get(orderId);
  if (currentRequest) {
    return currentRequest;
  }

  const request = api
    .get<EtaResponse>(`/api/delivery/orders/${orderId}/eta`)
    .then((data) => {
      etaCache.set(orderId, { data, updatedAt: Date.now() });
      return data;
    })
    .finally(() => {
      etaInFlight.delete(orderId);
    });

  etaInFlight.set(orderId, request);
  return request;
}

export function DeliveryEtaBadge({ orderId }: DeliveryEtaBadgeProps) {
  const [eta, setEta] = useState<EtaResponse | null>(null);

  const loadEta = useCallback(
    async (force = false) => {
      try {
        const data = await fetchOrderEta(orderId, force);
        setEta(data);
      } catch {
        setEta(null);
      }
    },
    [orderId],
  );

  useEffect(() => {
    void loadEta(false);

    const timer = window.setInterval(() => {
      void loadEta(true);
    }, 30_000);

    return () => window.clearInterval(timer);
  }, [loadEta]);

  if (!eta) {
    return null;
  }

  const minutes = Math.ceil(Math.max(eta.remaining_seconds, 0) / 60);

  if (eta.status === "ON_TIME") {
    return <Badge variant="success">⏱ {minutes} min restantes</Badge>;
  }

  if (eta.status === "ARRIVING") {
    return <Badge variant="warning">🚚 Chegando em {minutes} min</Badge>;
  }

  return <Badge variant="danger">⚠ Atrasado {minutes} min</Badge>;
}
