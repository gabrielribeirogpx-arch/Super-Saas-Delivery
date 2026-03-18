"use client";

import { useEffect, useMemo, useState } from "react";

import { normalizeTrackingStatus, resolveTrackingStep, TRACKING_STEPS } from "@/lib/orderTrackingStatus";
import { buildStorefrontApiUrl } from "@/lib/storefrontApi";
import { formatCurrencyFromCents } from "@/lib/currency";
import DeliveryProgressBar from "@/components/tracking/DeliveryProgressBar";

type TrackingItem = {
  name: string;
  quantity: number;
};

type TrackingPayload = {
  id?: number | string;
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
  last_location?: {
    lat?: number;
    lng?: number;
  } | null;
  progress?: number | null;
  distance_km?: number | null;
  eta_seconds?: number | null;
  customer_lat?: number | null;
  customer_lng?: number | null;
  delivery_lat?: number | null;
  delivery_lng?: number | null;
};

type TrackingRealtimePayload = {
  status?: string;
  status_raw?: string;
  status_step?: number;
  last_location?: {
    lat?: number;
    lng?: number;
  } | null;
  progress?: number | null;
  distance_km?: number | null;
  eta_seconds?: number | null;
  payload?: {
    status?: string;
    status_raw?: string;
    status_step?: number;
    last_location?: {
      lat?: number;
      lng?: number;
    } | null;
    progress?: number;
    distance_km?: number;
    eta_seconds?: number;
  };
};

export default function PublicOrderTrackingPage({ params }: { params: { token: string } }) {
  const [data, setData] = useState<TrackingPayload | null>(null);
  const [notFound, setNotFound] = useState(false);

  const color = useMemo(() => data?.primary_color || "#22c55e", [data?.primary_color]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    let eventSource: EventSource | null = null;

    const applyRealtimeStatus = (message: TrackingRealtimePayload) => {
      const payload = message.payload && typeof message.payload === "object" ? message.payload : message;
      const incomingRawStatus = String(payload.status_raw || payload.status || message.status_raw || message.status || "");
      const nextStatus = normalizeTrackingStatus(incomingRawStatus);
      const nextStatusStep = resolveTrackingStep(nextStatus, payload.status_step ?? message.status_step);
      const nextLocation = payload.last_location ?? message.last_location ?? null;
      const nextProgress = payload.progress ?? message.progress;
      const nextDistanceKm = payload.distance_km ?? message.distance_km;
      const nextEtaSeconds = payload.eta_seconds ?? message.eta_seconds;

      setData((prev) => {
        if (!prev) return prev;

        const resolvedStatus = incomingRawStatus ? nextStatus : prev.status;
        const isOutForDelivery = resolvedStatus === "delivering";

        return {
          ...prev,
          raw_status: incomingRawStatus || prev.raw_status,
          status: resolvedStatus,
          status_step: resolveTrackingStep(resolvedStatus, nextStatusStep || prev.status_step),
          last_location:
            nextLocation && Number.isFinite(Number(nextLocation.lat)) && Number.isFinite(Number(nextLocation.lng))
              ? { lat: Number(nextLocation.lat), lng: Number(nextLocation.lng) }
              : prev.last_location,
          progress: isOutForDelivery && Number.isFinite(Number(nextProgress)) ? Number(nextProgress) : 0,
          distance_km: isOutForDelivery && Number.isFinite(Number(nextDistanceKm)) ? Number(nextDistanceKm) : null,
          eta_seconds: isOutForDelivery && Number.isFinite(Number(nextEtaSeconds)) ? Number(nextEtaSeconds) : null,
        };
      });
    };

    const fetchTracking = async () => {
      try {
        const response = await fetch(buildStorefrontApiUrl(`/public/order/${params.token}`), {
          cache: "no-store",
          headers: {
            "Cache-Control": "no-cache",
            Pragma: "no-cache",
          },
        });
        if (response.status === 404) {
          setNotFound(true);
          return;
        }
        if (!response.ok) return;
        const payload = await response.json();
        const normalizedStatus = normalizeTrackingStatus(String(payload.status || "pending"));
        const isOutForDelivery = normalizedStatus === "delivering";

        setData({
          ...payload,
          raw_status: String(payload.status || ""),
          status: normalizedStatus,
          status_step: resolveTrackingStep(normalizedStatus, payload.status_step),
          progress: isOutForDelivery && Number.isFinite(Number(payload.progress)) ? Number(payload.progress) : 0,
          distance_km: isOutForDelivery && Number.isFinite(Number(payload.distance_km)) ? Number(payload.distance_km) : null,
          eta_seconds: isOutForDelivery && Number.isFinite(Number(payload.eta_seconds)) ? Number(payload.eta_seconds) : null,
        });
        setNotFound(false);
      } catch {
        // silencioso
      }
    };

    fetchTracking();

    eventSource = new EventSource(buildStorefrontApiUrl(`/public/sse/${params.token}`));
    eventSource.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as TrackingRealtimePayload;
        applyRealtimeStatus(parsed);
      } catch {
        // silencioso
      }
    };
    eventSource.onerror = () => {
      // o navegador faz retry automático; mantemos polling como fallback
    };

    interval = setInterval(fetchTracking, 15000);

    return () => {
      if (interval) clearInterval(interval);
      eventSource?.close();
    };
  }, [params.token]);

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

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-[430px]">
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
          <div className="text-center">
            {data?.store_logo_url ? <img src={data.store_logo_url} alt="Logo" className="mx-auto mb-2 h-12 w-12 rounded-full object-cover" /> : null}
            <p className="text-sm text-slate-500">{data?.store_name || "Restaurante"}</p>
            <h1 className="text-[28px] italic" style={{ fontFamily: "var(--font-display)" }}>
              Pedido #{data?.order_number || "--"}
            </h1>
          </div>

          {data ? <DeliveryProgressBar status={data.status} statusStep={data.status_step} progress={data.progress} distanceKm={data.distance_km} etaSeconds={data.eta_seconds} /> : null}

          <div className="space-y-2">
            {TRACKING_STEPS.map((step, index) => {
              const done = (data?.status_step || 1) >= index + 1;
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
              {data?.items?.map((item) => (
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
              <span>{formatCurrencyFromCents(Number(data?.total_cents ?? data?.total ?? 0))}</span>
            </div>
            <div className="mt-1 flex justify-between text-sm">
              <span>Pagamento</span>
              <span>{String(data?.payment_method || "-").toUpperCase()}</span>
            </div>
          </div>

          {data && normalizeTrackingStatus(String(data.status || "")) === "delivered" ? (
            <p className="text-center text-sm">Seu pedido foi entregue! Bom apetite 🍽️</p>
          ) : (
            <p className="text-center text-[11px] text-slate-500">Atualiza automaticamente em tempo real</p>
          )}
        </div>
      </div>
    </main>
  );
}
