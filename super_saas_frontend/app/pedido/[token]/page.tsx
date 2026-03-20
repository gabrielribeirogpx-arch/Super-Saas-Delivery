"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import CustomerTracking from "@/components/CustomerTracking";
import { formatCurrencyFromCents } from "@/lib/currency";
import { getCachedTrackingSnapshot, cacheTrackingSnapshot } from "@/lib/orderTrackingCache";
import { normalizeTrackingStatus, resolveTrackingStep, TRACKING_STEPS } from "@/lib/orderTrackingStatus";
import { resolveStorefrontTenant, storefrontFetch } from "@/lib/storefrontApi";

type ConnectionStatus = "live" | "stale";

type TrackingItem = {
  name: string;
  quantity: number;
};

type Coordinate = {
  lat?: number | null;
  lng?: number | null;
} | null;

type DeliveryAddress = {
  lat?: number | null;
  lng?: number | null;
  latitude?: number | null;
  longitude?: number | null;
} | null;

type LiveTrackingState = {
  driverLat?: number | null;
  driverLng?: number | null;
  distanceMeters: number | null;
  durationSeconds: number | null;
  progress: number | null;
};

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
  distance_meters?: number | null;
  duration_seconds?: number | null;
  remaining_seconds?: number | null;
  driver_lat?: number | null;
  driver_lng?: number | null;
  initial_distance_meters?: number | null;
  destination_lat?: number | null;
  destination_lng?: number | null;
  customer_lat?: number | null;
  customer_lng?: number | null;
  delivery_lat?: number | null;
  delivery_lng?: number | null;
  speed_mps?: number | null;
  delivery_address?: DeliveryAddress;
};

type TrackingRealtimePayload = {
  event?: string;
  status?: string;
  status_raw?: string;
  status_step?: number;
  last_location?: Coordinate;
  progress?: number | null;
  distance_meters?: number | null;
  duration_seconds?: number | null;
  remaining_seconds?: number | null;
  driver_lat?: number | null;
  driver_lng?: number | null;
  initial_distance_meters?: number | null;
  destination_lat?: number | null;
  destination_lng?: number | null;
  speed_mps?: number | null;
  payload?: {
    status?: string;
    status_raw?: string;
    status_step?: number;
    last_location?: Coordinate;
    progress?: number;
    distance_meters?: number;
    duration_seconds?: number;
    remaining_seconds?: number;
    driver_lat?: number;
    driver_lng?: number;
    initial_distance_meters?: number;
    destination_lat?: number;
    destination_lng?: number;
    speed_mps?: number;
  };
  data?: {
    event?: string;
    status?: string;
    status_raw?: string;
    status_step?: number;
    last_location?: Coordinate;
    progress?: number;
    distance_meters?: number;
    duration_seconds?: number;
    remaining_seconds?: number;
    driver_lat?: number;
    driver_lng?: number;
    initial_distance_meters?: number;
    destination_lat?: number;
    destination_lng?: number;
    speed_mps?: number;
  };
};

const LIVE_UPDATE_THRESHOLD_MS = 10_000;
const SSE_RECONNECT_DELAY_MS = 3_000;
const STATUS_CHECK_INTERVAL_MS = 2_000;
const POLLING_INTERVAL_MS = 15_000;
const STOPPED_SPEED_THRESHOLD_MPS = 0.3;
const TRACKING_FETCH_PATHS = ["/public/order", "/orders/by-token"] as const;

function isFiniteNumber(value: unknown): value is number {
  return Number.isFinite(Number(value));
}

function clampProgress(progress: number) {
  return Math.max(0, Math.min(1, progress));
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

function extractDestinationFromDeliveryAddress(address: unknown): { lat: number; lng: number } | null {
  if (!address || typeof address !== "object") {
    return null;
  }

  const candidate = address as Record<string, unknown>;
  const lat = candidate.latitude ?? candidate.lat;
  const lng = candidate.longitude ?? candidate.lng;

  if (!isFiniteNumber(lat) || !isFiniteNumber(lng)) {
    return null;
  }

  return { lat: Number(lat), lng: Number(lng) };
}

function orderLikeCustomerLat(order: TrackingPayload) {
  return order.customer_lat ?? order.delivery_address?.lat ?? order.delivery_address?.latitude ?? NaN;
}

function orderLikeCustomerLng(order: TrackingPayload) {
  return order.customer_lng ?? order.delivery_address?.lng ?? order.delivery_address?.longitude ?? NaN;
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
  const nextDistanceMeters = isFiniteNumber(source.distance_meters)
    ? Math.max(0, Math.round(Number(source.distance_meters)))
    : previous?.distance_meters ?? null;
  const resolvedDurationSeconds = source.duration_seconds ?? source.remaining_seconds;
  const nextDurationSeconds = isFiniteNumber(resolvedDurationSeconds)
    ? Math.max(0, Math.round(Number(resolvedDurationSeconds)))
    : previous?.duration_seconds ?? null;
  const nextLastLocation = normalizeCoordinate(source.last_location as Coordinate) ?? previous?.last_location ?? null;
  const derivedDriverLat = isFiniteNumber(source.driver_lat)
    ? Number(source.driver_lat)
    : nextLastLocation?.lat ?? previous?.driver_lat ?? null;
  const derivedDriverLng = isFiniteNumber(source.driver_lng)
    ? Number(source.driver_lng)
    : nextLastLocation?.lng ?? previous?.driver_lng ?? null;
  const shouldFreezeEta = isDelivered || Boolean(isCanceled) || (incomingSpeed !== null && incomingSpeed < STOPPED_SPEED_THRESHOLD_MPS);
  const previousDuration = previous?.duration_seconds ?? null;
  const initialDistanceMeters = isFiniteNumber(source.initial_distance_meters)
    ? Math.max(0, Math.round(Number(source.initial_distance_meters)))
    : previous?.initial_distance_meters ?? nextDistanceMeters;
  const calculatedProgress =
    initialDistanceMeters != null && nextDistanceMeters != null && initialDistanceMeters > 0
      ? clampProgress(1 - nextDistanceMeters / initialDistanceMeters)
      : incomingProgress;

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
    last_location: nextLastLocation,
    progress: isCanceled ? previous?.progress ?? 0 : isDelivered ? 1 : isOutForDelivery ? calculatedProgress : 0,
    distance_meters: isCanceled ? null : isOutForDelivery ? nextDistanceMeters : null,
    duration_seconds: isCanceled ? null : shouldFreezeEta ? previousDuration : isOutForDelivery ? nextDurationSeconds : null,
    driver_lat: isCanceled ? null : isOutForDelivery ? derivedDriverLat : null,
    driver_lng: isCanceled ? null : isOutForDelivery ? derivedDriverLng : null,
    initial_distance_meters: isCanceled ? null : isOutForDelivery ? initialDistanceMeters : null,
    destination_lat: isFiniteNumber(source.destination_lat) ? Number(source.destination_lat) : previous?.destination_lat ?? null,
    destination_lng: isFiniteNumber(source.destination_lng) ? Number(source.destination_lng) : previous?.destination_lng ?? null,
    customer_lat: isFiniteNumber(source.customer_lat) ? Number(source.customer_lat) : previous?.customer_lat ?? null,
    customer_lng: isFiniteNumber(source.customer_lng) ? Number(source.customer_lng) : previous?.customer_lng ?? null,
    delivery_lat: isFiniteNumber(source.delivery_lat) ? Number(source.delivery_lat) : previous?.delivery_lat ?? null,
    delivery_lng: isFiniteNumber(source.delivery_lng) ? Number(source.delivery_lng) : previous?.delivery_lng ?? null,
    speed_mps: incomingSpeed,
    delivery_address: extractDestinationFromDeliveryAddress(source.delivery_address) ?? previous?.delivery_address ?? null,
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

function buildTrackingSseUrl(token: string, tenant?: string | null) {
  const normalizedTenant = resolveStorefrontTenant(tenant);
  const encodedToken = encodeURIComponent(token);

  if (normalizedTenant) {
    return `/api/public/sse/${encodedToken}?tenant_id=${encodeURIComponent(normalizedTenant)}`;
  }

  return `/api/public/sse/${encodedToken}`;
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
  const [tracking, setTracking] = useState<LiveTrackingState | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [hasLiveSseData, setHasLiveSseData] = useState(false);
  const hasLiveSseDataRef = useRef(false);
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

    setTracking((prev) => ({
      ...prev,
      driverLat: data.driver_lat ?? prev?.driverLat,
      driverLng: data.driver_lng ?? prev?.driverLng,
      distanceMeters: data.distance_meters ?? prev?.distanceMeters ?? null,
      durationSeconds: data.duration_seconds ?? prev?.durationSeconds ?? null,
      progress: data.progress ?? prev?.progress ?? null,
    }));
  }, [data]);

  useEffect(() => {
    console.log("TRACKING STATE UPDATED:", tracking);
  }, [tracking]);

  useEffect(() => {
    hasLiveSseDataRef.current = hasLiveSseData;
  }, [hasLiveSseData]);

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
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const normalizedToken = decodeURIComponent(params.token || "").trim();
    const hasSnapshotBootstrap = Boolean(getCachedTrackingSnapshot(normalizedToken)?.payload);
    const hasBootstrapState = hasSnapshotBootstrap && Boolean(dataRef.current?.order_number || dataRef.current?.order_id);

    setHasLiveSseData(false);
    hasLiveSseDataRef.current = false;
    const now = Date.now();
    setLastUpdate(now);
    lastUpdateRef.current = now;
    setConnectionStatus("stale");
    setNotFound(false);

    let stopped = false;

    const stopRealtime = () => {
      stopped = true;
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
      }
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    };

    const applyRealtimeStatus = (message: TrackingRealtimePayload, payload: TrackingRealtimePayload) => {
      const payloadSource = payload.payload ?? payload.data ?? {};
      const mergedPayload = { ...message, ...payload, ...payloadSource };

      console.log("TRACKING EVENT RECEIVED:", mergedPayload);
      console.log("SSE DATA:", mergedPayload);

      const durationSeconds = mergedPayload.duration_seconds ?? mergedPayload.remaining_seconds;
      const distanceMeters = mergedPayload.distance_meters;
      const driverLat = mergedPayload.driver_lat;
      const driverLng = mergedPayload.driver_lng;
      const destinationLat = mergedPayload.destination_lat ?? null;
      const destinationLng = mergedPayload.destination_lng ?? null;
      const hasTrackingMetrics = distanceMeters != null || durationSeconds != null;
      const hasDriverLocation = driverLat != null && driverLng != null;

      console.log("SSE RAW:", mergedPayload);
      console.log("MAPPED:", {
        driverLat: mergedPayload.driver_lat,
        driverLng: mergedPayload.driver_lng,
      });

      if (!hasTrackingMetrics && !hasDriverLocation) {
        console.warn("INVALID PAYLOAD", mergedPayload);
        return;
      }

      console.log("Customer tracking SSE", {
        distance_meters: distanceMeters,
        duration_seconds: durationSeconds,
        driver_lat: driverLat,
        driver_lng: driverLng,
      });

      setTracking((prev) => {
        const nextTrackingState = {
          ...prev,
          driverLat: mergedPayload.driver_lat ?? prev?.driverLat,
          driverLng: mergedPayload.driver_lng ?? prev?.driverLng,
          distanceMeters: mergedPayload.distance_meters ?? prev?.distanceMeters ?? null,
          durationSeconds: (mergedPayload.duration_seconds ?? mergedPayload.remaining_seconds) ?? prev?.durationSeconds ?? null,
          progress: mergedPayload.progress ?? prev?.progress ?? null,
        };

        console.log("STATE AFTER:", nextTrackingState);

        return nextTrackingState;
      });

      setData((prev) => {
        if (!prev) {
          return prev;
        }

        return createSafeTrackingState(
          {
            ...prev,
            ...message,
            ...payload,
            ...payloadSource,
            driver_lat: driverLat,
            driver_lng: driverLng,
            distance_meters: distanceMeters,
            duration_seconds: durationSeconds,
            destination_lat: destinationLat ?? prev.destination_lat,
            destination_lng: destinationLng ?? prev.destination_lng,
            last_location:
              driverLat != null && driverLng != null
                ? { lat: Number(driverLat), lng: Number(driverLng) }
                : (mergedPayload.last_location ?? prev.last_location),
          },
          prev,
        );
      });
      setNotFound(false);
    };

    const openRealtime = () => {
      if (eventSourceRef.current || stopped || !normalizedToken) {
        return;
      }

      const resolvedTenant =
        typeof window !== "undefined" ? resolveStorefrontTenant(new URLSearchParams(window.location.search).get("tenant")) : null;
      const streamUrl = buildTrackingSseUrl(normalizedToken, resolvedTenant);
      if (!streamUrl) {
        return;
      }

      try {
        const eventSource = new EventSource(streamUrl);
        eventSourceRef.current = eventSource;

        const handleTrackingUpdate = (event: MessageEvent<string>) => {
          try {
            const payload = JSON.parse(event.data) as TrackingRealtimePayload;
            const now = Date.now();

            setHasLiveSseData(true);
            hasLiveSseDataRef.current = true;
            setLastUpdate(now);
            lastUpdateRef.current = now;
            setConnectionStatus("live");
            applyRealtimeStatus(payload, payload);
          } catch (error) {
            console.error("SSE PARSE ERROR", error);
          }
        };

        eventSource.onopen = () => {
          console.log("SSE CONNECTED");
        };
        eventSource.addEventListener("tracking_update", handleTrackingUpdate as EventListener);
        eventSource.addEventListener("driver_update", handleTrackingUpdate as EventListener);
        eventSource.onerror = (error) => {
          console.error("SSE ERROR", error);
          eventSource.close();
          if (eventSourceRef.current === eventSource) {
            eventSourceRef.current = null;
          }
          if (!stopped) {
            reconnectTimeout = setTimeout(() => {
              reconnectTimeout = null;
              openRealtime();
            }, SSE_RECONNECT_DELAY_MS);
          }
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

      const shouldPreserveLiveTracking =
        hasLiveSseDataRef.current
        && dataRef.current?.distance_meters != null
        && dataRef.current?.duration_seconds != null
        && (nextState.distance_meters == null || nextState.duration_seconds == null);

      setData(shouldPreserveLiveTracking ? dataRef.current : nextState);
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

      setConnectionStatus(diff < LIVE_UPDATE_THRESHOLD_MS ? "live" : "stale");
    }, STATUS_CHECK_INTERVAL_MS);

    return () => {
      isMounted = false;
      clearInterval(startupRetryInterval);
      if (interval) clearInterval(interval);
      if (statusInterval) clearInterval(statusInterval);
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
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
    hasLiveSseDataRef.current = false;
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
      case "stale":
        return "Sem atualização recente";
      default:
        return "Atualizando em tempo real";
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

  const destinationLat = Number(orderLikeCustomerLat(data));
  const destinationLng = Number(orderLikeCustomerLng(data));

  console.log("DESTINATION RAW:", data);
  console.log("DESTINATION:", destinationLat, destinationLng);

  if (
    Number.isFinite(destinationLat)
    && Number.isFinite(destinationLng)
    && (
      Math.abs(destinationLat) > 90
      || Math.abs(destinationLng) > 180
    )
  ) {
    console.error("Invalid destination coordinates");
  }

  const order = {
    ...data,
    status: data.raw_status ?? data.status,
    destinationLocation:
      Number.isFinite(destinationLat) && Number.isFinite(destinationLng)
        ? { lat: destinationLat, lng: destinationLng }
        : null,
    liveUpdatesEnabled: connectionStatus === "live" && !realtimeStopped,
    isOffline: false,
  };
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

          <CustomerTracking order={order} tracking={tracking} />

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
