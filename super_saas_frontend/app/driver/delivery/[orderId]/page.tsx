"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import DeliveryMap from "@/components/driver/DeliveryMap";
import { completeOrder, getDriverState, sendDriverLocation, startOrder } from "@/services/driverApi";

type ToastType = "started" | "completed";

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
  const [customerLat, setCustomerLat] = useState<number | null>(null);
  const [customerLng, setCustomerLng] = useState<number | null>(null);
  const [customerAddress, setCustomerAddress] = useState<string | null>(null);
  const [navigationMode, setNavigationMode] = useState(false);
  const [eta, setEta] = useState<string | null>(null);
  const [distance, setDistance] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastType | null>(null);
  const [completing, setCompleting] = useState(false);
  const [hideCard, setHideCard] = useState(false);
  const watchIdRef = useRef<number | null>(null);

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
  }, [orderId]);

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
  }, [orderId]);

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
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
          setFeedback("Invalid geolocation data");
          return;
        }

        setDriverLat(lat);
        setDriverLng(lng);
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
    await startOrder(orderId);
    setStatus("OUT_FOR_DELIVERY");
    setNavigationMode(true);
    setToast("started");
  };

  const handleComplete = async () => {
    await completeOrder(orderId);
    setStatus("DELIVERED");
    setNavigationMode(false);
    setCompleting(true);
    setToast("completed");
    setTimeout(() => setHideCard(true), 700);
    setTimeout(() => router.push("/driver/dashboard"), 1350);
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-slate-950 text-white">
      <DeliveryMap
        orderId={orderId}
        driverLat={driverLat}
        driverLng={driverLng}
        customerLat={customerLat}
        customerLng={customerLng}
        customerAddress={customerAddress}
        navigationMode={navigationMode}
        onMetricsChange={({ eta: currentEta, distance: currentDistance }) => {
          setEta(currentEta);
          setDistance(currentDistance);
        }}
      />

      <div className="pointer-events-none absolute inset-x-0 top-0 z-20 p-4">
        {!hideCard && (
          <div
            className={`mx-auto w-full max-w-md rounded-2xl border border-white/30 bg-black/70 p-4 backdrop-blur transition-all duration-500 ${
              completing ? "translate-y-2 opacity-0" : "translate-y-0 opacity-100"
            }`}
          >
            <p className="text-xs uppercase tracking-wide text-slate-300">Delivery #{orderId}</p>
            <p className="mt-1 text-sm text-slate-200">Status: <strong>{status}</strong></p>
            <div className="mt-2 flex justify-between text-sm">
              <p>ETA: <strong>{eta ?? "--"}</strong></p>
              <p>Distance: <strong>{distance ?? "--"}</strong></p>
            </div>
          </div>
        )}
      </div>

      {!hideCard && (
        <div
          className={`absolute bottom-5 left-1/2 z-20 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 rounded-2xl border border-white/30 bg-black/70 p-3 shadow-xl backdrop-blur transition-all duration-500 ${
            completing ? "translate-y-20 opacity-0" : "translate-y-0 opacity-100"
          }`}
        >
          <div className="mb-3 flex items-center justify-between">
            <button className="text-sm text-blue-200" onClick={() => router.push("/driver/dashboard")}>Back</button>
            {geoBlocked && <p className="text-xs text-amber-300">GPS blocked</p>}
          </div>
          <button
            className="mb-2 w-full rounded-xl bg-amber-500 p-3 text-sm font-semibold text-slate-950 disabled:opacity-50"
            onClick={handleStart}
            disabled={navigationMode || status === "OUT_FOR_DELIVERY" || status === "DELIVERED"}
          >
            START DELIVERY
          </button>
          <button
            className="w-full rounded-xl bg-emerald-500 p-3 text-sm font-semibold text-slate-950 disabled:opacity-50"
            onClick={handleComplete}
            disabled={status === "DELIVERED"}
          >
            COMPLETE DELIVERY
          </button>
          {completing && <p className="mt-3 text-center text-base font-semibold text-emerald-200">✓ Delivery Completed</p>}
        </div>
      )}

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
