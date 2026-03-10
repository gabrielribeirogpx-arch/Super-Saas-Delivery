"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import DriverLayout from "@/components/driver/DriverLayout";
import DeliveryMap from "@/components/driver/DeliveryMap";
import { completeOrder, getDriverState, sendDriverLocation, startOrder } from "@/services/driverApi";

type ToastType = "started" | "completed";

const TOAST_COPY: Record<ToastType, string> = {
  started: "Delivery Started",
  completed: "Delivery Completed",
};

export default function DriverDeliveryPage() {
  const params = useParams<{ orderId: string }>();
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
    setTimeout(() => setHideCard(true), 500);
  };

  return (
    <DriverLayout title={`Delivery #${orderId}`}>
      <p className="mb-2 text-sm">Current status: <strong>{status}</strong></p>
      {!hideCard && (
        <div className={`mb-3 space-y-2 rounded-lg border border-slate-200 bg-white p-3 shadow-sm transition-all duration-500 ${completing ? "translate-y-2 opacity-0" : "translate-y-0 opacity-100"}`}>
          <button className="w-full rounded bg-amber-600 p-3 text-white disabled:opacity-60" onClick={handleStart} disabled={navigationMode || status === "OUT_FOR_DELIVERY" || status === "DELIVERED"}>
            START DELIVERY
          </button>
          <button className="w-full rounded bg-green-700 p-3 text-white disabled:opacity-60" onClick={handleComplete} disabled={status === "DELIVERED"}>
            COMPLETE DELIVERY
          </button>
          {completing && <p className="text-center text-sm font-semibold text-emerald-700">✓ Delivery Completed</p>}
        </div>
      )}
      <DeliveryMap
        orderId={orderId}
        driverLat={driverLat}
        driverLng={driverLng}
        customerLat={customerLat}
        customerLng={customerLng}
        customerAddress={customerAddress}
        navigationMode={navigationMode}
      />
      {feedback && <p className="mt-3 rounded bg-slate-100 p-2 text-sm text-slate-700">{feedback}</p>}
      <div className={`fixed bottom-5 left-1/2 z-50 -translate-x-1/2 rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-lg transition-all duration-300 ${toast ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0 pointer-events-none"}`}>
        {toast ? TOAST_COPY[toast] : ""}
      </div>
    </DriverLayout>
  );
}
