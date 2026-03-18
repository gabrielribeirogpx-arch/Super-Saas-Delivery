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
  payload?: {
    status?: string;
    status_raw?: string;
    status_step?: number;
    last_location?: {
      lat?: number;
      lng?: number;
    } | null;
  };
};

export default function PublicOrderTrackingPage({ params }: { params: { token: string } }) {
  const [data, setData] = useState<TrackingPayload | null>(null);
  const [notFound, setNotFound] = useState(false);

  const color = useMemo(() => data?.primary_color || "#22c55e", [data?.primary_color]);
  const isOutForDelivery =
    String(data?.raw_status || "").toUpperCase() === "OUT_FOR_DELIVERY" || normalizeTrackingStatus(String(data?.status || "")) === "delivering";


  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    let eventSource: EventSource | null = null;

    const applyRealtimeStatus = (message: TrackingRealtimePayload) => {
      const payload = message.payload && typeof message.payload === "object" ? message.payload : message;
      const incomingRawStatus = String(payload.status_raw || payload.status || message.status_raw || message.status || "");
      const nextStatus = normalizeTrackingStatus(incomingRawStatus);
      const nextStatusStep = resolveTrackingStep(nextStatus, payload.status_step ?? message.status_step);
      const nextLocation = payload.last_location ?? message.last_location ?? null;

      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          raw_status: incomingRawStatus || prev.raw_status,
          status: incomingRawStatus ? nextStatus : prev.status,
          status_step: nextStatusStep || prev.status_step,
          last_location:
            nextLocation && Number.isFinite(Number(nextLocation.lat)) && Number.isFinite(Number(nextLocation.lng))
              ? { lat: Number(nextLocation.lat), lng: Number(nextLocation.lng) }
              : prev.last_location,
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

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!isOutForDelivery) return;
    if ((window as Window & { ORDER_STATUS?: string }).ORDER_STATUS !== "OUT_FOR_DELIVERY") return;

    const GOOGLE_MAPS_SCRIPT_ID = "google-maps-js";
    const GOOGLE_MAPS_API_KEY = "AIzaSyCDi9WNbfW843u-GyJy4RNYWQ_2VDTrQiY";
    const browserWindow = window as unknown as {
      google?: any;
      __googleMapsScriptLoadingPromise?: Promise<void>;
      ORDER_STATUS?: string;
      ORDER_TOKEN?: string;
    };

    const loadGoogleMaps = async () => {
      if (browserWindow.google?.maps) {
        return;
      }

      if (browserWindow.__googleMapsScriptLoadingPromise) {
        return browserWindow.__googleMapsScriptLoadingPromise;
      }

      browserWindow.__googleMapsScriptLoadingPromise = new Promise<void>((resolve, reject) => {
        const existingScript = document.getElementById(GOOGLE_MAPS_SCRIPT_ID) as HTMLScriptElement | null;
        if (existingScript) {
          if (browserWindow.google?.maps) {
            resolve();
            return;
          }
          existingScript.addEventListener(
            "load",
            () => {
              if (browserWindow.google?.maps) {
                resolve();
                return;
              }
              reject(new Error("Google Maps não foi inicializado"));
            },
            { once: true },
          );
          existingScript.addEventListener("error", () => reject(new Error("Google Maps indisponível")), { once: true });
          return;
        }

        const script = document.createElement("script");
        script.id = GOOGLE_MAPS_SCRIPT_ID;
        script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(GOOGLE_MAPS_API_KEY)}`;
        script.async = true;
        script.defer = true;

        script.onload = () => {
          if (browserWindow.google?.maps) {
            resolve();
            return;
          }
          reject(new Error("Google Maps não foi inicializado"));
        };
        script.onerror = () => reject(new Error("Erro ao carregar Google Maps"));

        document.head.appendChild(script);
      });

      return browserWindow.__googleMapsScriptLoadingPromise;
    };

    let map: any = null;
    let driverMarker: any = null;
    let animationFrame: number | null = null;
    let isDestroyed = false;
    let currentPosition = {
      lat: Number(data?.last_location?.lat ?? -23.5505),
      lng: Number(data?.last_location?.lng ?? -46.6333),
    };

    const animateMarkerMovement = (target: { lat: number; lng: number }) => {
      if (!driverMarker || !map || !browserWindow.google?.maps) return;

      if (animationFrame !== null) {
        window.cancelAnimationFrame(animationFrame);
      }

      const start = { ...currentPosition };
      const startTime = performance.now();
      const duration = 800;

      const step = (now: number) => {
        const progress = Math.min((now - startTime) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const lat = start.lat + (target.lat - start.lat) * eased;
        const lng = start.lng + (target.lng - start.lng) * eased;
        const nextPos = { lat, lng };

        driverMarker.setPosition(nextPos);
        map.panTo(nextPos);

        if (progress < 1) {
          animationFrame = window.requestAnimationFrame(step);
          return;
        }

        currentPosition = target;
        animationFrame = null;
      };

      animationFrame = window.requestAnimationFrame(step);
    };

    const initTrackingMap = () => {
      if (isDestroyed) return;
      if (!browserWindow.google?.maps) return;

      const mapContainer = document.getElementById("tracking-map");
      if (!mapContainer) return;

      const customerLat = Number(data?.customer_lat ?? data?.delivery_lat ?? data?.last_location?.lat ?? -23.5505);
      const customerLng = Number(data?.customer_lng ?? data?.delivery_lng ?? data?.last_location?.lng ?? -46.6333);
      const customerPosition = {
        lat: Number.isFinite(customerLat) ? customerLat : -23.5505,
        lng: Number.isFinite(customerLng) ? customerLng : -46.6333,
      };

      currentPosition = {
        lat: Number(data?.last_location?.lat ?? customerPosition.lat),
        lng: Number(data?.last_location?.lng ?? customerPosition.lng),
      };

      map = new browserWindow.google.maps.Map(mapContainer, {
        center: customerPosition,
        zoom: 14,
        disableDefaultUI: true,
        mapTypeControl: false,
        fullscreenControl: false,
        streetViewControl: false,
      });

      const deliveryIcon = {
        path: browserWindow.google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
        fillColor: "#22c55e",
        fillOpacity: 1,
        strokeColor: "#14532d",
        strokeWeight: 1,
        scale: 6,
        rotation: 0,
      };

      driverMarker = new browserWindow.google.maps.Marker({
        map,
        position: currentPosition,
        title: "Entregador",
        icon: deliveryIcon,
      });

      return;
    };

    const bootMap = async () => {
      try {
        await loadGoogleMaps();
      } catch {
        return;
      }

      initTrackingMap();
    };

    const initWhenReady = () => {
      void bootMap();
    };

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initWhenReady, { once: true });
    } else {
      initWhenReady();
    }

    return () => {
      isDestroyed = true;
      document.removeEventListener("DOMContentLoaded", initWhenReady);
      if (animationFrame !== null) {
        window.cancelAnimationFrame(animationFrame);
      }
      if (driverMarker) {
        driverMarker.setMap(null);
      }
      map = null;
    };
  }, [data?.customer_lat, data?.customer_lng, data?.delivery_lat, data?.delivery_lng, data?.last_location?.lat, data?.last_location?.lng, isOutForDelivery]);

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
        {isOutForDelivery ? <div id="tracking-map" style={{ height: "420px", width: "100%", borderRadius: "16px", marginBottom: "20px" }} /> : null}

        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
          <div className="text-center">
            {data?.store_logo_url ? <img src={data.store_logo_url} alt="Logo" className="mx-auto mb-2 h-12 w-12 rounded-full object-cover" /> : null}
            <p className="text-sm text-slate-500">{data?.store_name || "Restaurante"}</p>
            <h1 className="text-[28px] italic" style={{ fontFamily: "var(--font-display)" }}>
              Pedido #{data?.order_number || "--"}
            </h1>
          </div>

          {data ? <DeliveryProgressBar status={data.raw_status || data.status} statusStep={data.status_step} /> : null}

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
