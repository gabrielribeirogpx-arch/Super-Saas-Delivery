"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import DeliveryMap from "@/components/driver/DeliveryMap";
import { completeOrder, getDriverState, sendDriverLocation, startOrder } from "@/services/driverApi";
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
  const params = useParams<{ orderId: string }>();
  const router = useRouter();
  const orderId = Number(params.orderId);
  const [status, setStatus] = useState("DRIVER_ASSIGNED");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [geoBlocked, setGeoBlocked] = useState(false);
  const [driverLat, setDriverLat] = useState<number | null>(null);
  const [driverLng, setDriverLng] = useState<number | null>(null);
  const [driverHeading, setDriverHeading] = useState<number | null>(null);
  const [driverSpeed, setDriverSpeed] = useState<number | null>(null);
  const [destinationLat, setDestinationLat] = useState<number | null>(null);
  const [destinationLng, setDestinationLng] = useState<number | null>(null);
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
  const watchIdRef = useRef<number | null>(null);

  const persistNavigationState = (nextState: PersistedNavigationState) => {
    if (typeof window === "undefined") {
      return;
    }

    localStorage.setItem(NAV_STATE_STORAGE_KEY, JSON.stringify(nextState));
  };

  useEffect(() => {
    setDestinationLat(null);
    setDestinationLng(null);
    setCustomerAddress(null);
    setStatus("DRIVER_ASSIGNED");
    setNavigationMode(false);
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
      setDestinationLat(parsed.destination.lat);
      setDestinationLng(parsed.destination.lng);
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
      destination: { lat: destinationLat, lng: destinationLng, address: customerAddress },
      routeCoordinates,
      eta,
      distance,
    });
  }, [orderId, status, navigationMode, driverLat, driverLng, destinationLat, destinationLng, customerAddress, routeCoordinates, eta, distance]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timer = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    const syncDriverState = async () => {
      try {
        const state = await getDriverState();
        if (state.active_delivery?.id === orderId) {
          setStatus(state.active_delivery.status);
          setDestinationLat(state.active_delivery.lat ?? null);
          setDestinationLng(state.active_delivery.lng ?? null);
          setCustomerAddress(state.active_delivery.address ?? null);
        } else {
          if (navigationMode || status === "OUT_FOR_DELIVERY") {
            return;
          }
          setDestinationLat(null);
          setDestinationLng(null);
          setCustomerAddress(null);
        }
      } catch {
        setFeedback(t("backend_unavailable"));
      }
    };

    void syncDriverState();
    const timer = setInterval(syncDriverState, 2000);

    return () => {
      clearInterval(timer);
    };
  }, [orderId, navigationMode, status]);

  useEffect(() => {
    if (!navigationMode) {
      if (watchIdRef.current !== null) {
        navigator.geolocation?.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
      return;
    }

    if (!navigator.geolocation) {
      setGeoBlocked(true);
      setFeedback(t("geolocation_not_supported"));
      return;
    }

    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        const lat = position.coords.latitude;
        const lng = position.coords.longitude;
        const heading = position.coords.heading;
        const speed = position.coords.speed;
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
          setFeedback(t("invalid_geolocation_data"));
          return;
        }

        setDriverLat(lat);
        setDriverLng(lng);
        setDriverHeading(Number.isFinite(heading) ? heading : null);
        setDriverSpeed(Number.isFinite(speed) ? speed : null);
        setFeedback(null);
        sendDriverLocation({ order_id: orderId, lat, lng }).catch(() => setFeedback(t("location_update_failed")));
      },
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          setGeoBlocked(true);
          setFeedback(t("location_permission_denied"));
          return;
        }

        setFeedback(t("unable_to_read_location"));
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      },
    );

    watchIdRef.current = watchId;

    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
    };
  }, [navigationMode, orderId]);

  const handleStart = async () => {
    if (!isMapInitialized) {
      setFeedback(t("map_initializing"));
      return;
    }

    if (navigator.geolocation) {
      await new Promise<void>((resolve) => {
        navigator.geolocation.getCurrentPosition(
          (position) => {
            setDriverLat(position.coords.latitude);
            setDriverLng(position.coords.longitude);
            resolve();
          },
          () => resolve(),
          { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
        );
      });
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
    <main className="relative min-h-screen overflow-hidden bg-slate-950 text-white">
      <DeliveryMap
        orderId={orderId}
        driverLat={driverLat}
        driverLng={driverLng}
        driverHeading={driverHeading}
        driverSpeed={driverSpeed}
        destinationLat={destinationLat}
        destinationLng={destinationLng}
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
            </div>
            <div className="flex flex-col gap-3">
              <button
                className="w-full rounded-2xl bg-amber-500 px-4 py-4 text-sm font-semibold tracking-wide text-slate-950 disabled:opacity-50"
                onClick={handleStart}
                disabled={!isMapInitialized || navigationMode || status === "OUT_FOR_DELIVERY" || status === "DELIVERED"}
              >
                {t("start_delivery")}
              </button>
              <button
                className="w-full rounded-2xl bg-emerald-500 px-4 py-4 text-sm font-semibold tracking-wide text-slate-950 disabled:opacity-50"
                onClick={handleComplete}
                disabled={status === "DELIVERED"}
              >
                {t("complete_delivery")}
              </button>
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
  );
}
