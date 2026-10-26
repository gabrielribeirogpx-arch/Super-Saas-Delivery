"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";

export type DeliveryEtaStatus = "ON_TIME" | "ARRIVING" | "DELAYED";

interface DeliveryEtaResponse {
  remaining_seconds: number;
  status: DeliveryEtaStatus;
}

interface DeliveryEtaState {
  remainingSeconds: number | null;
  status: DeliveryEtaStatus | null;
  loading: boolean;
}

const ETA_POLLING_INTERVAL_MS = 30_000;
const ETA_CACHE_TTL_MS = 25_000;

const etaCache = new Map<number, { data: DeliveryEtaResponse; updatedAt: number }>();
const etaInFlight = new Map<number, Promise<DeliveryEtaResponse>>();

export function useDeliveryEta(orderId: number): DeliveryEtaState {
  const [state, setState] = useState<DeliveryEtaState>({
    remainingSeconds: null,
    status: null,
    loading: true,
  });

  const isMountedRef = useRef(true);

  const fetchEta = useCallback(async (force = false): Promise<DeliveryEtaResponse> => {
    const cached = etaCache.get(orderId);
    const now = Date.now();

    if (!force && cached && now - cached.updatedAt < ETA_CACHE_TTL_MS) {
      return cached.data;
    }

    const existingRequest = etaInFlight.get(orderId);
    if (existingRequest) {
      return existingRequest;
    }

    const request = api
      .get<DeliveryEtaResponse>(`/api/delivery/orders/${orderId}/eta`)
      .then((data) => {
        etaCache.set(orderId, { data, updatedAt: Date.now() });
        return data;
      })
      .finally(() => {
        etaInFlight.delete(orderId);
      });

    etaInFlight.set(orderId, request);

    return request;
  }, [orderId]);

  const loadEta = useCallback(async (force = false) => {
    try {
      const data = await fetchEta(force);

      if (!isMountedRef.current) {
        return;
      }

      setState({
        remainingSeconds: data.remaining_seconds,
        status: data.status,
        loading: false,
      });
    } catch {
      if (!isMountedRef.current) {
        return;
      }

      setState({
        remainingSeconds: null,
        status: null,
        loading: false,
      });
    }
  }, [fetchEta]);

  useEffect(() => {
    isMountedRef.current = true;
    setState({ remainingSeconds: null, status: null, loading: true });

    void loadEta(false);

    const interval = window.setInterval(() => {
      void loadEta(true);
    }, ETA_POLLING_INTERVAL_MS);

    return () => {
      isMountedRef.current = false;
      window.clearInterval(interval);
    };
  }, [loadEta]);

  return state;
}
