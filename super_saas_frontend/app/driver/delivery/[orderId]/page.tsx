"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import DeliveryMap from "@/components/driver/DeliveryMap";
import DriverAuthGuard from "@/components/driver/DriverAuthGuard";
import { completeOrder, getDriverState, startOrder, DriverOrder } from "@/services/driverApi";
import { driverLocationService } from "@/services/driverLocationService";
import { buildGoogleMapsUrl, buildTelUrl, buildWazeUrl, buildWhatsAppUrl } from "@/services/driverNavigation";
import { t, tStatus } from "@/i18n/translate";

type ToastType = "started" | "completed";

const NAV_STATE_STORAGE_KEY = "driver-active-navigation";

type PersistedNavigationState = {
  activeDeliveryId: number;
  status: string;
  navigationMode: boolean;
  driverLocation: { lat: number | null; lng: number | null };
  destination: { lat: number | null; lng: number | null; address: string | null };
  routeCoordinates: [number, number][];
  eta: string | null;
  distance: string | null;
};

export default function DriverDeliveryPage() {
  const params = useParams<{ orderId?: string; id?: string }>();
  const router = useRouter();
  const orderId = Number(params.orderId ?? params.id);
  const [orderDetails, setOrderDetails] = useState<DriverOrder | null>(null);
  const [status, setStatus] = useState("DRIVER_ASSIGNED");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [geoBlocked, setGeoBlocked] = useState(false);
  const [driverLat, setDriverLat] = useState<number | null>(null);
  const [driverLng, setDriverLng] = useState<number | null>(null);
  const [driverHeading, setDriverHeading] = useState<number | null>(null);
  const [driverSpeed, setDriverSpeed] = useState<number | null>(null);
  const [customerLat, setCustomerLat] = useState<number | null>(null);
  const [customerLng, setCustomerLng] = useState<number | null>(null);
  const [customerAddress, setCustomerAddress] = useState<string | null>(null);
  const [navigationMode, setNavigationMode] = useState(false);
  const [eta, setEta] = useState<string | null>(null);
  const [distance, setDistance] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastType | null>(null);
  const [completing, setCompleting] = useState(false);
  const [hideCard, setHideCard] = useState(false);
  const [routeCoordinates, setRouteCoordinates] = useState<[number, number][]>([]);
  const [isMapInitialized, setIsMapInitialized] = useState(false);
  const [isFollowing, setIsFollowing] = useState(false);

  const persistNavigationState = (nextState: PersistedNavigationState) => {
    if (typeof window === "undefined") {
      return;
    }

    localStorage.setItem(NAV_STATE_STORAGE_KEY, JSON.stringify(nextState));
  };

  useEffect(() => {
    setCustomerLat(null);
    setCustomerLng(null);
    setCustomerAddress(null);
    setStatus("DRIVER_ASSIGNED");
    setNavigationMode(false);
    driverLocationService.stop();
    setCompleting(false);
    setHideCard(false);
    setEta(null);
    setDistance(null);
    setRouteCoordinates([]);
    setIsMapInitialized(false);
    setIsFollowing(false);
  }, [orderId]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const raw = localStorage.getItem(NAV_STATE_STORAGE_KEY);
    if (!raw) {
      return;
    }

    try {
      const parsed = JSON.parse(raw) as PersistedNavigationState;
      if (parsed.activeDeliveryId !== orderId) {
        return;
      }

      setStatus(parsed.status);
      setNavigationMode(parsed.navigationMode);
      setDriverLat(parsed.driverLocation.lat);
      setDriverLng(parsed.driverLocation.lng);
      setCustomerLat(parsed.destination.lat);
      setCustomerLng(parsed.destination.lng);
      setCustomerAddress(parsed.destination.address);
      setRouteCoordinates(parsed.routeCoordinates ?? []);
      setEta(parsed.eta);
      setDistance(parsed.distance);
      setIsFollowing(parsed.navigationMode);
    } catch {
      localStorage.removeItem(NAV_STATE_STORAGE_KEY);
    }
  }, [orderId]);

  useEffect(() => {
    persistNavigationState({
      activeDeliveryId: orderId,
      status,
      navigationMode,
      driverLocation: { lat: driverLat, lng: driverLng },
      destination: { lat: customerLat, lng: customerLng, address: customerAddress },
      routeCoordinates,
      eta,
      distance,
    });
  }, [orderId, status, navigationMode, driverLat, driverLng, customerLat, customerLng, customerAddress, routeCoordinates, eta, distance]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timer = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const state = await getDriverState();
        if (state.active_delivery?.id === orderId) {
          setStatus(state.active_delivery.status);
          setCustomerLat(state.active_delivery.customer_lat ?? null);
          setCustomerLng(state.active_delivery.customer_lng ?? null);
          setCustomerAddress(state.active_delivery.address ?? null);
          setOrderDetails(state.active_delivery);
        } else {
          if (navigationMode || status === "OUT_FOR_DELIVERY") {
            return;
          }
          setCustomerLat(null);
          setCustomerLng(null);
          setCustomerAddress(null);
        }
      } catch {
        setFeedback(t("backend_unavailable"));
      }
    }, 2000);

    return () => {
      clearInterval(timer);
    };
  }, [orderId, navigationMode, status]);

  useEffect(() => {
    if (!navigationMode || status === "DELIVERED") {
      driverLocationService.stop();
      return;
    }

    driverLocationService.start({
      deliveryId: orderId,
      onLocation: (sample) => {
        setDriverLat(sample.latitude);
        setDriverLng(sample.longitude);
        setDriverHeading(sample.heading);
        setDriverSpeed(sample.speed);
        setFeedback(null);
      },
      onError: (message) => {
        setGeoBlocked(message.toLowerCase().includes("negada"));
        setFeedback(message);
      },
    });

    return () => {
      driverLocationService.stop();
    };
  }, [navigationMode, orderId, status]);

  const handleStart = async () => {
    if (!isMapInitialized) {
      setFeedback(t("map_initializing"));
      return;
    }

    try {
      const position = await driverLocationService.getCurrentPosition();
      setDriverLat(position.coords.latitude);
      setDriverLng(position.coords.longitude);
    } catch (error: any) {
      setFeedback(error?.message || t("location_permission_denied"));
    }

    await startOrder(orderId);
    setStatus("OUT_FOR_DELIVERY");
    startNavigation();
    setToast("started");
  };

  const startNavigation = () => {
    setNavigationMode(true);
    setIsFollowing(true);
  };

  const handleComplete = async () => {
    await completeOrder(orderId);
    setStatus("DELIVERED");
    setNavigationMode(false);
    setIsFollowing(false);
    setCompleting(true);
    setToast("completed");
    if (typeof window !== "undefined") {
      localStorage.removeItem(NAV_STATE_STORAGE_KEY);
    }
    setTimeout(() => setHideCard(true), 700);
    setTimeout(() => router.push("/driver/dashboard"), 1350);
  };

  return (
    <DriverAuthGuard>
      <main className="relative min-h-screen overflow-hidden bg-slate-950 text-white">
      <DeliveryMap
        orderId={orderId}
        driverLat={driverLat}
        driverLng={driverLng}
        driverHeading={driverHeading}
        driverSpeed={driverSpeed}
        customerLat={customerLat}
        customerLng={customerLng}
        customerAddress={customerAddress}
        navigationMode={navigationMode}
        initialRouteCoordinates={routeCoordinates}
        onRouteChange={(coordinates) => {
          if (coordinates.length === 0) {
            return;
          }

          setRouteCoordinates((prev) => {
            const prevFirst = prev[0];
            const nextFirst = coordinates[0];
            const prevLast = prev.at(-1);
            const nextLast = coordinates.at(-1);
            const unchanged =
              prev.length === coordinates.length &&
              prevFirst?.[0] === nextFirst?.[0] &&
              prevFirst?.[1] === nextFirst?.[1] &&
              prevLast?.[0] === nextLast?.[0] &&
              prevLast?.[1] === nextLast?.[1];

            return unchanged ? prev : coordinates;
          });
        }}
        onMapReadyChange={(ready) => {
          setIsMapInitialized(ready);
        }}
        onRecenter={() => {
          setNavigationMode(true);
          setIsFollowing(true);
        }}
        onOverview={() => {
          setNavigationMode(false);
          setIsFollowing(false);
        }}
        onFollowModeChange={(next) => {
          setIsFollowing(next);
          if (next) {
            setNavigationMode(true);
          }
        }}
        onMetricsChange={({ eta: currentEta, distance: currentDistance }) => {
          setEta((prev) => (prev === currentEta ? prev : currentEta));
          setDistance((prev) => (prev === currentDistance ? prev : currentDistance));
        }}
      />

      <div className="pointer-events-none absolute inset-x-0 top-0 z-20 p-3 sm:p-4">
        {!hideCard && (
          <div
            className={`mx-auto flex w-full max-w-md items-center justify-between gap-3 rounded-2xl border border-white/45 bg-white/90 px-3 py-2 text-slate-900 shadow-lg backdrop-blur-md transition-all duration-500 max-h-[60px] ${
              completing ? "translate-y-2 opacity-0" : "translate-y-0 opacity-100"
            }`}
          >
              <p className="truncate text-xs sm:text-sm text-slate-700">
              {t("status")}: <strong className="text-slate-900">{tStatus(status)}</strong>
            </p>
            <div className="flex items-center gap-3 text-xs sm:text-sm">
              <p className="whitespace-nowrap">
                {t("eta")}: <strong>{eta ?? "--"}</strong>
              </p>
              <p className="whitespace-nowrap">
                {t("distance")}: <strong>{distance ?? "--"}</strong>
              </p>
            </div>
          </div>
        )}
      </div>

      {!hideCard && (
        <div
          className={`absolute inset-x-0 bottom-0 z-20 px-3 pb-[max(0.9rem,env(safe-area-inset-bottom))] sm:px-4 ${
            completing ? "pointer-events-none" : ""
          }`}
        >
          <div
            className={`mx-auto w-full max-w-md rounded-2xl border border-white/30 bg-black/65 p-3 shadow-xl backdrop-blur transition-all duration-500 ${
              completing ? "translate-y-20 opacity-0" : "translate-y-0 opacity-100"
            }`}
          >
            <div className="mb-3 flex items-center justify-between">
              <button className="text-sm text-blue-200" onClick={() => router.push("/driver/dashboard")}>{t("back")}</button>
              {geoBlocked && <p className="text-xs text-amber-300">{t("gps_blocked")}</p>}
              {navigationMode && <p className="text-xs text-emerald-300">● Localização ativa com o app aberto</p>}
            </div>
            <div className="flex flex-col gap-3">
              <div className="rounded-2xl bg-white/10 p-3 text-sm text-slate-100">
                <p className="font-semibold">{orderDetails?.customer_name || "Cliente"}</p>
                <p>{orderDetails?.phone || "Telefone não informado"}</p>
                <p className="mt-1">{customerAddress || "Endereço não informado"}</p>
                {orderDetails?.complement && <p>Complemento: {orderDetails.complement}</p>}
                {orderDetails?.reference && <p>Referência: {orderDetails.reference}</p>}
                {orderDetails?.notes && <p>Obs.: {orderDetails.notes}</p>}
                <p>Pagamento: {orderDetails?.payment_method || "--"} {orderDetails?.change_for ? `(troco para ${orderDetails.change_for})` : ""}</p>
                {orderDetails?.items && <details className="mt-2"><summary>Itens</summary><pre className="whitespace-pre-wrap text-xs">{orderDetails.items}</pre></details>}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <a className="rounded-xl bg-blue-600 px-3 py-3 text-center text-sm font-bold text-white" target="_blank" href={buildGoogleMapsUrl({ latitude: customerLat, longitude: customerLng, address: customerAddress })}>Google Maps</a>
                <a className="rounded-xl bg-cyan-600 px-3 py-3 text-center text-sm font-bold text-white" target="_blank" href={buildWazeUrl({ latitude: customerLat, longitude: customerLng, address: customerAddress })}>Waze</a>
                <a className={`rounded-xl px-3 py-3 text-center text-sm font-bold ${buildTelUrl(orderDetails?.phone) ? "bg-slate-100 text-slate-950" : "bg-slate-700 text-slate-400 pointer-events-none"}`} href={buildTelUrl(orderDetails?.phone) || undefined}>Ligar</a>
                <a className={`rounded-xl px-3 py-3 text-center text-sm font-bold ${buildWhatsAppUrl(orderDetails?.phone) ? "bg-green-500 text-slate-950" : "bg-slate-700 text-slate-400 pointer-events-none"}`} target="_blank" href={buildWhatsAppUrl(orderDetails?.phone) || undefined}>WhatsApp</a>
              </div>

              <button
                className="w-full rounded-2xl bg-amber-500 px-4 py-4 text-sm font-semibold tracking-wide text-slate-950 disabled:opacity-50"
                onClick={handleStart}
                disabled={!isMapInitialized || navigationMode || status === "OUT_FOR_DELIVERY" || status === "DELIVERED"}
              >
                {status === "DRIVER_ASSIGNED" ? t("start_delivery") : "Iniciar rastreamento"}
              </button>
              <button
                className="w-full rounded-2xl bg-emerald-500 px-4 py-4 text-sm font-semibold tracking-wide text-slate-950 disabled:opacity-50"
                onClick={handleComplete}
                disabled={status === "DELIVERED"}
              >
                Marcar como entregue
              </button>
              <button className="w-full rounded-2xl bg-white/10 px-4 py-4 text-sm font-semibold text-white" onClick={() => setFeedback("Chegada registrada visualmente. Status definitivo exige endpoint dedicado em fase futura.")}>Cheguei ao local</button>
              <button className="w-full rounded-2xl bg-red-500/80 px-4 py-4 text-sm font-semibold text-white" onClick={() => setFeedback("Problema registrado para contato com a loja. Persistência será adicionada em endpoint dedicado.")}>Reportar problema</button>
            </div>
            {completing && <p className="mt-3 text-center text-base font-semibold text-emerald-200">✓ {t("delivery_completed")}</p>}
          </div>
        </div>
      )}

      <button
        type="button"
        className="absolute bottom-36 right-3 z-30 rounded-full border border-white/40 bg-slate-900/70 px-4 py-3 text-sm font-semibold text-white shadow-xl backdrop-blur sm:right-4"
        onClick={() => router.push("/driver/dashboard")}
      >
        📦 {t("orders")}
      </button>

      {feedback && <p className="absolute left-4 top-32 z-20 rounded-lg bg-black/65 px-3 py-2 text-xs text-slate-200">{feedback}</p>}

      <div
        className={`fixed bottom-28 left-1/2 z-50 -translate-x-1/2 rounded-full bg-slate-900/95 px-4 py-2 text-sm font-medium text-white shadow-lg transition-all duration-300 ${
          toast ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-3 opacity-0"
        }`}
      >
        {toast ? (toast === "started" ? t("navigation_started") : t("delivery_completed")) : ""}
      </div>
      </main>
    </DriverAuthGuard>
  );
}
