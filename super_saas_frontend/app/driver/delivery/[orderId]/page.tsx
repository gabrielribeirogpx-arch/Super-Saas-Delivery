"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import DeliveryMap from "@/components/driver/DeliveryMap";
import { completeOrder, getDriverState, sendDriverLocation, startOrder } from "@/services/driverApi";

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
  instruction: string | null;
  instructionDistance: string | null;
};

const TOAST_COPY: Record<ToastType, string> = {
  started: "Navigation Started",
  completed: "Delivery Completed",
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
  const [instruction, setInstruction] = useState<string | null>(null);
  const [instructionDistance, setInstructionDistance] = useState<string | null>(null);
  const watchIdRef = useRef<number | null>(null);

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
    setCompleting(false);
    setHideCard(false);
    setEta(null);
    setDistance(null);
    setRouteCoordinates([]);
    setIsMapInitialized(false);
    setInstruction(null);
    setInstructionDistance(null);
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
      setInstruction(parsed.instruction ?? null);
      setInstructionDistance(parsed.instructionDistance ?? null);
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
      instruction,
      instructionDistance,
    });
  }, [orderId, status, navigationMode, driverLat, driverLng, customerLat, customerLng, customerAddress, routeCoordinates, eta, distance, instruction, instructionDistance]);

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
        } else {
          if (navigationMode || status === "OUT_FOR_DELIVERY") {
            return;
          }
          setCustomerLat(null);
          setCustomerLng(null);
          setCustomerAddress(null);
        }
      } catch {
        setFeedback("Backend unavailable");
      }
    }, 2000);

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
      setFeedback("Geolocation not supported on this device");
      return;
    }

    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        const lat = position.coords.latitude;
        const lng = position.coords.longitude;
        const heading = position.coords.heading;
        const speed = position.coords.speed;
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
          setFeedback("Invalid geolocation data");
          return;
        }

        setDriverLat(lat);
        setDriverLng(lng);
        setDriverHeading(Number.isFinite(heading) ? heading : null);
        setDriverSpeed(Number.isFinite(speed) ? speed : null);
        setFeedback(null);
        sendDriverLocation({ order_id: orderId, lat, lng }).catch(() => setFeedback("Location update failed"));
      },
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          setGeoBlocked(true);
          setFeedback("Location permission denied. Location updates paused.");
          return;
        }

        setFeedback("Unable to read your location");
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
      setFeedback("Map is still initializing");
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
        onNavigationUpdate={({ instruction: nextInstruction, instructionDistance: nextInstructionDistance }) => {
          setInstruction((prev) => (prev === nextInstruction ? prev : nextInstruction));
          setInstructionDistance((prev) => (prev === nextInstructionDistance ? prev : nextInstructionDistance));
        }}
      />

      <div className="pointer-events-none absolute inset-x-0 top-0 z-20 p-3 sm:p-4">
        {!hideCard && (
          <div
            className={`mx-auto w-full max-w-md rounded-2xl border border-white/45 bg-white/85 p-4 text-slate-900 shadow-lg backdrop-blur-md transition-all duration-500 ${
              completing ? "translate-y-2 opacity-0" : "translate-y-0 opacity-100"
            }`}
          >
            <p className="text-xs uppercase tracking-wide text-slate-600">Delivery #{orderId}</p>
            <p className="mt-1 text-sm text-slate-700">
              Status: <strong className="text-slate-900">{status}</strong>
            </p>
            <div className="mt-2 flex justify-between text-sm">
              <p>
                ETA: <strong>{eta ?? "--"}</strong>
              </p>
              <p>
                Distance: <strong>{distance ?? "--"}</strong>
              </p>
            </div>
            <div className="mt-3 rounded-xl bg-slate-900 px-3 py-2 text-sm text-white">
              <p className="text-[11px] uppercase tracking-wide text-blue-200">Next turn</p>
              <p className="mt-1 font-semibold">{instruction ?? "Continue straight"}</p>
              <p className="text-xs text-slate-300">{instructionDistance ?? "--"}</p>
            </div>
            <p className="mt-2 text-[11px] text-slate-600">Mode: {isFollowing ? "FOLLOW" : "FREE MAP"}</p>
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
              <button className="text-sm text-blue-200" onClick={() => router.push("/driver/dashboard")}>Back</button>
              {geoBlocked && <p className="text-xs text-amber-300">GPS blocked</p>}
            </div>
            <div className="flex flex-col gap-3">
              <button
                className="w-full rounded-2xl bg-amber-500 px-4 py-4 text-sm font-semibold tracking-wide text-slate-950 disabled:opacity-50"
                onClick={handleStart}
                disabled={!isMapInitialized || navigationMode || status === "OUT_FOR_DELIVERY" || status === "DELIVERED"}
              >
                START DELIVERY
              </button>
              <button
                className="w-full rounded-2xl bg-emerald-500 px-4 py-4 text-sm font-semibold tracking-wide text-slate-950 disabled:opacity-50"
                onClick={handleComplete}
                disabled={status === "DELIVERED"}
              >
                COMPLETE DELIVERY
              </button>
            </div>
            {completing && <p className="mt-3 text-center text-base font-semibold text-emerald-200">✓ Delivery Completed</p>}
          </div>
        </div>
      )}

      <button
        type="button"
        className="absolute bottom-36 right-3 z-30 rounded-full border border-white/40 bg-slate-900/70 px-4 py-3 text-sm font-semibold text-white shadow-xl backdrop-blur sm:right-4"
        onClick={() => router.push("/driver/dashboard")}
      >
        📦 Orders
      </button>

      {feedback && <p className="absolute left-4 top-32 z-20 rounded-lg bg-black/65 px-3 py-2 text-xs text-slate-200">{feedback}</p>}

      <div
        className={`fixed bottom-28 left-1/2 z-50 -translate-x-1/2 rounded-full bg-slate-900/95 px-4 py-2 text-sm font-medium text-white shadow-lg transition-all duration-300 ${
          toast ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-3 opacity-0"
        }`}
      >
        {toast ? TOAST_COPY[toast] : ""}
      </div>
    </main>
  );
}
