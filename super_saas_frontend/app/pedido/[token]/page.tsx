"use client";

import { useEffect, useMemo, useState } from "react";
import Script from "next/script";

import { normalizeTrackingStatus, resolveTrackingStep, TRACKING_STEPS } from "@/lib/orderTrackingStatus";
import { buildStorefrontApiUrl, buildStorefrontWebSocketUrl } from "@/lib/storefrontApi";
import { formatCurrencyFromCents } from "@/lib/currency";

type TrackingItem = {
  name: string;
  quantity: number;
};

type TrackingPayload = {
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
};

type TrackingRealtimePayload = {
  status?: string;
  status_raw?: string;
  status_step?: number;
};

export default function PublicOrderTrackingPage({ params }: { params: { token: string } }) {
  const [data, setData] = useState<TrackingPayload | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [leafletReady, setLeafletReady] = useState(false);

  const color = useMemo(() => data?.primary_color || "#22c55e", [data?.primary_color]);
  const isOutForDelivery =
    String(data?.raw_status || "").toUpperCase() === "OUT_FOR_DELIVERY" || normalizeTrackingStatus(String(data?.status || "")) === "delivering";

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    let socket: WebSocket | null = null;

    const applyRealtimeStatus = (payload: TrackingRealtimePayload) => {
      const incomingRawStatus = String(payload.status_raw || payload.status || "");
      const nextStatus = normalizeTrackingStatus(incomingRawStatus);
      const nextStatusStep = resolveTrackingStep(nextStatus, payload.status_step);

      if (!nextStatusStep) {
        return;
      }

      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          raw_status: incomingRawStatus || prev.raw_status,
          status: nextStatus,
          status_step: nextStatusStep,
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
        setData({
          ...payload,
          raw_status: String(payload.status || ""),
          status: normalizeTrackingStatus(String(payload.status || "pending")),
          status_step: resolveTrackingStep(String(payload.status || "pending"), payload.status_step),
        });
        setNotFound(false);
      } catch {
        // silencioso
      }
    };

    fetchTracking();

    const websocketUrl = buildStorefrontWebSocketUrl(`/ws/public/tracking/${params.token}`);
    if (websocketUrl) {
      socket = new WebSocket(websocketUrl);
      socket.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data) as TrackingRealtimePayload;
          applyRealtimeStatus(parsed);
        } catch {
          // silencioso
        }
      };
    }

    interval = setInterval(fetchTracking, 15000);

    return () => {
      if (interval) clearInterval(interval);
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, [params.token]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    (window as Window & { ORDER_STATUS?: string; ORDER_TOKEN?: string }).ORDER_STATUS = String(data?.raw_status || "").toUpperCase();
    (window as Window & { ORDER_STATUS?: string; ORDER_TOKEN?: string }).ORDER_TOKEN = params.token;
  }, [data?.raw_status, params.token]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!leafletReady || !isOutForDelivery) return;
    if ((window as Window & { ORDER_STATUS?: string }).ORDER_STATUS !== "OUT_FOR_DELIVERY") return;

    const mapContainer = document.getElementById("tracking-map");
    const browserWindow = window as unknown as { L?: any; ORDER_STATUS?: string; ORDER_TOKEN?: string };
    if (!mapContainer || !browserWindow.L) return;

    const L = browserWindow.L;
    const initialLat = Number(data?.last_location?.lat ?? -23.5505);
    const initialLng = Number(data?.last_location?.lng ?? -46.6333);
    const initialPosition: [number, number] = [initialLat, initialLng];

    const map = L.map("tracking-map", {
      zoomControl: true,
      attributionControl: true,
    }).setView(initialPosition, 15);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    const driverMarker = L.marker(initialPosition).addTo(map);
    let evtSource: EventSource | null = null;

    try {
      const orderToken = browserWindow.ORDER_TOKEN;
      if (!orderToken) {
        return () => {
          map.remove();
        };
      }

      evtSource = new EventSource(`/sse/order/${orderToken}`);

      evtSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data || "{}") as { type?: string; lat?: number; lng?: number };

          if (payload.type === "tracking_ended") {
            evtSource?.close();
            return;
          }

          const nextLat = Number(payload.lat);
          const nextLng = Number(payload.lng);
          if (Number.isNaN(nextLat) || Number.isNaN(nextLng)) return;

          driverMarker.setLatLng([nextLat, nextLng]);
          map.panTo([nextLat, nextLng], { animate: true, duration: 0.75 });
        } catch {
          // silencioso
        }
      };

      evtSource.onerror = () => {
        evtSource?.close();
      };
    } catch {
      // silencioso
    }

    return () => {
      evtSource?.close();
      map.remove();
    };
  }, [data?.last_location?.lat, data?.last_location?.lng, isOutForDelivery, leafletReady]);

  if (notFound) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <div className="w-full max-w-[430px] rounded-2xl border border-slate-200 bg-white p-6 text-center">Pedido não encontrado</div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
      <Script src="https://unpkg.com/leaflet/dist/leaflet.js" strategy="afterInteractive" onLoad={() => setLeafletReady(true)} />

      <div className="w-full max-w-[430px]">
        {isOutForDelivery ? <div id="tracking-map" style={{ height: "420px", width: "100%", borderRadius: "16px", marginBottom: "20px" }} /> : null}

        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
          <div className="text-center">
            {data?.store_logo_url ? <img src={data.store_logo_url} alt="Logo" className="mx-auto mb-2 h-12 w-12 rounded-full object-cover" /> : null}
            <p className="text-sm text-slate-500">{data?.store_name || "Restaurante"}</p>
            <h1 className="text-[28px] italic" style={{ fontFamily: "var(--font-display)" }}>
              Pedido #{data?.order_number || "--"}
            </h1>
          </div>

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
