"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import CustomerTrackingProgress from "@/components/CustomerTrackingProgress";
import { formatCurrencyFromCents } from "@/lib/currency";
import { getCachedTrackingSnapshot, cacheTrackingSnapshot } from "@/lib/orderTrackingCache";
import { normalizeTrackingStatus, resolveTrackingStep, TRACKING_STEPS } from "@/lib/orderTrackingStatus";
import { buildStorefrontEventStreamUrl, resolveStorefrontTenant, storefrontFetch } from "@/lib/storefrontApi";

type ConnectionStatus = "live" | "delayed" | "offline";

type TrackingItem = {
  name: string;
  quantity: number;
};

type Coordinate = {
  lat?: number | null;
  lng?: number | null;
} | null;

type TrackingPayload = {
  id?: number | string;
  order_id?: number;
  order_number: number;
  status: string;
  raw_status?: string;
  status_step: number;
  payment_method: string | null;
  total: number;
  total_cents?: number;
  items: TrackingItem[];
  store_name: string | null;
  store_logo_url: string | null;
  primary_color: string | null;
  last_location?: Coordinate;
  progress?: number | null;
  distance_km?: number | null;
  eta_seconds?: number | null;
  customer_lat?: number | null;
  customer_lng?: number | null;
  delivery_lat?: number | null;
  delivery_lng?: number | null;
  speed_mps?: number | null;
};

type TrackingRealtimePayload = {
  status?: string;
  status_raw?: string;
  status_step?: number;
  last_location?: Coordinate;
  progress?: number | null;
  distance_km?: number | null;
  eta_seconds?: number | null;
  speed_mps?: number | null;
  payload?: {
    status?: string;
    status_raw?: string;
    status_step?: number;
    last_location?: Coordinate;
    progress?: number;
    distance_km?: number;
    eta_seconds?: number;
    speed_mps?: number;
  };
};

const OFFLINE_AFTER_MS = 20_000;
const DELAYED_AFTER_MS = 5_000;
const STATUS_CHECK_INTERVAL_MS = 2_000;
const POLLING_INTERVAL_MS = 15_000;
const STOPPED_SPEED_THRESHOLD_MPS = 0.3;
const TRACKING_FETCH_PATHS = ["/public/order", "/orders/by-token"] as const;
const TRACKING_SSE_PATHS = ["/public/sse", "/sse/delivery"] as const;

function isFiniteNumber(value: unknown): value is number {
  return Number.isFinite(Number(value));
}

function normalizeCoordinate(point: Coordinate | undefined): { lat: number; lng: number } | null {
  if (!point) {
    return null;
  }

  const lat = Number(point.lat);
  const lng = Number(point.lng);

  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return null;
  }

  return { lat, lng };
}

function normalizeItems(items: unknown): TrackingItem[] {
  if (!Array.isArray(items)) {
    return [];
  }

  return items.flatMap((item) => {
    if (!item || typeof item !== "object") {
      return [];
    }

    const name = typeof (item as { name?: unknown }).name === "string" ? (item as { name: string }).name : "Item";
    const quantity = Number((item as { quantity?: unknown }).quantity);

    return [{ name, quantity: Number.isFinite(quantity) && quantity > 0 ? quantity : 1 }];
  });
}

function createSafeTrackingState(payload: unknown, previous: TrackingPayload | null = null): TrackingPayload | null {
  if (!payload || typeof payload !== "object") {
    return previous;
  }

  const source = payload as Record<string, unknown>;
  const rawStatus = String(source.status_raw ?? source.status ?? previous?.raw_status ?? previous?.status ?? "pending");
  const normalizedStatus = normalizeTrackingStatus(rawStatus);
  const normalizedStep = resolveTrackingStep(normalizedStatus, source.status_step as number | null | undefined);
  const isDelivered = normalizedStatus === "delivered";
  const isCanceled = normalizedStatus === "canceled" || rawStatus.trim().toLowerCase() === "cancelado";
  const isOutForDelivery = normalizedStatus === "delivering";
  const fallbackProgress = isDelivered ? 1 : previous?.progress ?? 0;
  const incomingProgress = isFiniteNumber(source.progress) ? Math.max(0, Math.min(1, Number(source.progress))) : fallbackProgress;
  const incomingSpeed = isFiniteNumber(source.speed_mps) ? Number(source.speed_mps) : previous?.speed_mps ?? null;
  const shouldFreezeEta = isDelivered || Boolean(isCanceled) || (incomingSpeed !== null && incomingSpeed < STOPPED_SPEED_THRESHOLD_MPS);
  const previousEta = previous?.eta_seconds ?? null;
  const nextEta = isFiniteNumber(source.eta_seconds)
    ? Math.max(0, Math.round(Number(source.eta_seconds)))
    : previousEta;

  return {
    id:
      typeof source.id === "string" || typeof source.id === "number"
        ? source.id
        : previous?.id,
    order_id: isFiniteNumber(source.order_id) ? Number(source.order_id) : previous?.order_id,
    order_number: isFiniteNumber(source.order_number) ? Number(source.order_number) : previous?.order_number ?? 0,
    status: isCanceled ? "canceled" : normalizedStatus,
    raw_status: rawStatus,
    status_step: isCanceled ? previous?.status_step ?? normalizedStep : normalizedStep,
    payment_method: typeof source.payment_method === "string" ? source.payment_method : previous?.payment_method ?? null,
    total: isFiniteNumber(source.total) ? Number(source.total) : previous?.total ?? 0,
    total_cents: isFiniteNumber(source.total_cents) ? Number(source.total_cents) : previous?.total_cents,
    items: normalizeItems(source.items ?? previous?.items),
    store_name: typeof source.store_name === "string" ? source.store_name : previous?.store_name ?? null,
    store_logo_url: typeof source.store_logo_url === "string" ? source.store_logo_url : previous?.store_logo_url ?? null,
    primary_color: typeof source.primary_color === "string" ? source.primary_color : previous?.primary_color ?? null,
    last_location: normalizeCoordinate(source.last_location as Coordinate) ?? previous?.last_location ?? null,
    progress: isCanceled ? previous?.progress ?? 0 : isDelivered ? 1 : isOutForDelivery ? incomingProgress : 0,
    distance_km: isCanceled ? null : isOutForDelivery && isFiniteNumber(source.distance_km) ? Number(source.distance_km) : previous?.distance_km ?? null,
    eta_seconds: isCanceled ? null : shouldFreezeEta ? previousEta : isOutForDelivery ? nextEta : null,
    customer_lat: isFiniteNumber(source.customer_lat) ? Number(source.customer_lat) : previous?.customer_lat ?? null,
    customer_lng: isFiniteNumber(source.customer_lng) ? Number(source.customer_lng) : previous?.customer_lng ?? null,
    delivery_lat: isFiniteNumber(source.delivery_lat) ? Number(source.delivery_lat) : previous?.delivery_lat ?? null,
    delivery_lng: isFiniteNumber(source.delivery_lng) ? Number(source.delivery_lng) : previous?.delivery_lng ?? null,
    speed_mps: incomingSpeed,
  };
}

function shouldStopRealtime(status: string | null | undefined) {
  const normalized = normalizeTrackingStatus(String(status || ""));
  return normalized === "delivered" || normalized === "canceled";
}

async function fetchTrackingSnapshot(token: string) {
  for (const basePath of TRACKING_FETCH_PATHS) {
    try {
      const response = await storefrontFetch(`${basePath}/${encodeURIComponent(token)}`, {
        cache: "no-store",
        headers: {
          "Cache-Control": "no-cache",
          Pragma: "no-cache",
        },
      });

      if (response.status === 404) {
        continue;
      }

      if (!response.ok) {
        return { response, payload: null };
      }

      return { response, payload: await response.json() };
    } catch {
      continue;
    }
  }

  return { response: null, payload: null };
}

function buildTrackingSseUrl(token: string) {
  for (const basePath of TRACKING_SSE_PATHS) {
    try {
      return buildStorefrontEventStreamUrl(`${basePath}/${encodeURIComponent(token)}`);
    } catch {
      // tenta próximo caminho compatível
    }
  }

  return null;
}

function buildFallbackTrackingState(token: string) {
  if (typeof window === "undefined") {
    return null;
  }

  const normalizedToken = decodeURIComponent(token || "").trim();
  const cachedSnapshot = getCachedTrackingSnapshot(normalizedToken);

  if (!cachedSnapshot?.payload) {
    return null;
  }

  return createSafeTrackingState(cachedSnapshot.payload, null);
}

export default function PublicOrderTrackingPage({ params }: { params: { token: string } }) {
  const [data, setData] = useState<TrackingPayload | null>(() => buildFallbackTrackingState(params.token));
  const [notFound, setNotFound] = useState(false);
  const [hasLiveSseData, setHasLiveSseData] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(() => Date.now());
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("live");
  const eventSourceRef = useRef<EventSource | null>(null);
  const lastUpdateRef = useRef(Date.now());
  const dataRef = useRef<TrackingPayload | null>(data);

  const color = useMemo(() => data?.primary_color || "#22c55e", [data?.primary_color]);
  const isDelivered = normalizeTrackingStatus(String(data?.status || "")) === "delivered";
  const isCanceled = String(data?.status || "").trim().toLowerCase() === "canceled";
  const realtimeStopped = isDelivered || isCanceled;

  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  useEffect(() => {
    if (!data) {
      return;
    }

    const normalizedToken = decodeURIComponent(params.token || "").trim();
    if (!normalizedToken) {
      return;
    }

    const resolvedTenant =
      typeof window !== "undefined" ? resolveStorefrontTenant(new URLSearchParams(window.location.search).get("tenant")) : null;

    cacheTrackingSnapshot({
      token: normalizedToken,
      tenant: resolvedTenant,
      payload: data as unknown as Record<string, unknown>,
    });
  }, [data, params.token]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    let statusInterval: ReturnType<typeof setInterval> | null = null;
    let isMounted = true;
    let consecutiveMissingResponses = 0;
    let startupRetries = 0;

    const normalizedToken = decodeURIComponent(params.token || "").trim();
    const hasSnapshotBootstrap = Boolean(getCachedTrackingSnapshot(normalizedToken)?.payload);
    const hasBootstrapState = hasSnapshotBootstrap && Boolean(dataRef.current?.order_number || dataRef.current?.order_id);

    setHasLiveSseData(false);
    const now = Date.now();
    setLastUpdate(now);
    lastUpdateRef.current = now;
    setConnectionStatus("live");
    setNotFound(false);

    let stopped = false;

    const stopRealtime = () => {
      stopped = true;
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    };

    const applyRealtimeStatus = (message: TrackingRealtimePayload) => {
      const payload = message.payload && typeof message.payload === "object" ? message.payload : message;

      setData((prev) => {
        if (!prev) {
          return prev;
        }

        return createSafeTrackingState({ ...prev, ...payload, ...message }, prev);
      });
      setNotFound(false);
    };

    const openRealtime = () => {
      if (eventSourceRef.current || stopped || !normalizedToken) {
        return;
      }

      const streamUrl = buildTrackingSseUrl(normalizedToken);
      if (!streamUrl) {
        return;
      }

      try {
        eventSourceRef.current = new EventSource(streamUrl);
        eventSourceRef.current.onmessage = (event) => {
          try {
            const parsed = JSON.parse(event.data) as TrackingRealtimePayload;
            setHasLiveSseData(true);
            const now = Date.now();
            setLastUpdate(now);
            lastUpdateRef.current = now;
            setConnectionStatus("live");
            applyRealtimeStatus(parsed);
          } catch {
            // ignorar payload inválido para não quebrar a UI
          }
        };
        eventSourceRef.current.onerror = () => {
          // o navegador faz retry automático; mantemos polling como fallback
        };
      } catch {
        // silencioso
      }
    };

    const fetchTracking = async () => {
      if (stopped || !normalizedToken) {
        return false;
      }

      const { response, payload } = await fetchTrackingSnapshot(normalizedToken);

      if (!isMounted) {
        return false;
      }

      if (!response) {
        return false;
      }

      if (response.status === 404) {
        consecutiveMissingResponses += 1;
        if (!dataRef.current && consecutiveMissingResponses >= 6) {
          setNotFound(true);
          stopRealtime();
        }
        return false;
      }

      if (!response.ok || !payload) {
        return false;
      }

      const nextState = createSafeTrackingState(payload, dataRef.current);

      if (!nextState || !nextState.order_number) {
        return false;
      }

      consecutiveMissingResponses = 0;
      setData(nextState);
      setNotFound(false);
      const updateTs = Date.now();
      setLastUpdate(updateTs);
      lastUpdateRef.current = updateTs;

      if (shouldStopRealtime(nextState.status)) {
        stopRealtime();
        return true;
      }

      openRealtime();
      return true;
    };

    if (hasBootstrapState) {
      if (!shouldStopRealtime(dataRef.current?.status)) {
        openRealtime();
      }
    } else {
      void fetchTracking();
    }

    const startupRetryInterval = setInterval(() => {
      if (stopped || startupRetries >= 5 || dataRef.current) {
        clearInterval(startupRetryInterval);
        return;
      }

      startupRetries += 1;
      void fetchTracking();
    }, 2_500);
    interval = setInterval(() => {
      void fetchTracking();
    }, POLLING_INTERVAL_MS);

    statusInterval = setInterval(() => {
      const diff = Date.now() - lastUpdateRef.current;

      if (diff < DELAYED_AFTER_MS) {
        setConnectionStatus("live");
      } else if (diff < OFFLINE_AFTER_MS) {
        setConnectionStatus("delayed");
      } else {
        setConnectionStatus("offline");
      }
    }, STATUS_CHECK_INTERVAL_MS);

    return () => {
      isMounted = false;
      clearInterval(startupRetryInterval);
      if (interval) clearInterval(interval);
      if (statusInterval) clearInterval(statusInterval);
      stopRealtime();
    };
  }, [params.token]);

  useEffect(() => {
    if (!data || !shouldStopRealtime(data.status)) {
      return;
    }

    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setHasLiveSseData(false);
  }, [data]);

  const getStatusLabel = (status: ConnectionStatus) => {
    if (isCanceled) {
      return "Pedido cancelado";
    }

    if (isDelivered) {
      return "Pedido entregue";
    }

    switch (status) {
      case "live":
        return "🟢 Atualizando em tempo real";
      case "delayed":
        return "🟡 Sem atualização recente";
      case "offline":
        return "🔴 Entregador offline";
      default:
        return "🟢 Atualizando em tempo real";
    }
  };

  useEffect(() => {
    if (typeof window === "undefined") return;

    (window as Window & { ORDER_STATUS?: string; ORDER_TOKEN?: string }).ORDER_STATUS = String(data?.raw_status || "").toUpperCase();
    (window as Window & { ORDER_STATUS?: string; ORDER_TOKEN?: string }).ORDER_TOKEN = params.token;
  }, [data?.raw_status, params.token]);

  if (notFound) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <div className="w-full max-w-[430px] rounded-2xl border border-slate-200 bg-white p-6 text-center">Pedido não encontrado</div>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <div className="w-full max-w-[430px] rounded-2xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
          Carregando rastreamento do pedido...
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-[430px]">
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
          <div className="text-center">
            {data.store_logo_url ? <img src={data.store_logo_url} alt="Logo" className="mx-auto mb-2 h-12 w-12 rounded-full object-cover" /> : null}
            <p className="text-sm text-slate-500">{data.store_name || "Restaurante"}</p>
            <h1 className="text-[28px] italic" style={{ fontFamily: "var(--font-display)" }}>
              Pedido #{data.order_number || data.order_id || "--"}
            </h1>
          </div>

          <CustomerTrackingProgress
            order={{
              ...data,
              destinationLocation: { lat: data.customer_lat ?? data.delivery_lat, lng: data.customer_lng ?? data.delivery_lng },
              liveUpdatesEnabled: hasLiveSseData && connectionStatus === "live" && !realtimeStopped,
              isOffline: connectionStatus === "offline",
            }}
          />

          <div className="space-y-2">
            {TRACKING_STEPS.map((step, index) => {
              const done = isCanceled ? false : (data.status_step || 1) >= index + 1;
              return (
                <div key={step.key} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block h-3 w-3 rounded-full border ${done ? "border-transparent" : "border-slate-300"}`}
                      style={{ backgroundColor: done ? color : "transparent" }}
                    />
                    <span>{step.label}</span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="rounded-xl border border-slate-200 p-4">
            <p className="mb-2 text-sm font-semibold">Resumo do pedido</p>
            <div className="space-y-1 text-sm">
              {data.items?.map((item) => (
                <div key={`${item.name}-${item.quantity}`} className="flex justify-between">
                  <span>
                    {item.quantity}x {item.name}
                  </span>
                </div>
              ))}
            </div>
            <div className="my-3 h-px bg-slate-200" />
            <div className="flex justify-between text-sm">
              <span>Total</span>
              <span>{formatCurrencyFromCents(Number(data.total_cents ?? data.total ?? 0))}</span>
            </div>
            <div className="mt-1 flex justify-between text-sm">
              <span>Pagamento</span>
              <span>{String(data.payment_method || "-").toUpperCase()}</span>
            </div>
          </div>

          {isCanceled ? (
            <p className="text-center text-sm font-medium text-rose-600">Pedido cancelado</p>
          ) : isDelivered ? (
            <p className="text-center text-sm">Seu pedido foi entregue! Bom apetite 🍽️</p>
          ) : (
            <p className="text-center text-[11px] text-slate-500">
              {getStatusLabel(connectionStatus)} • atualizado há {Math.max(0, Math.round((Date.now() - lastUpdate) / 1000))}s
            </p>
          )}
        </div>
      </div>
    </main>
  );

}