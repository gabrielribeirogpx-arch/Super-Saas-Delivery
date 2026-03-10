"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import DriverLayout from "@/components/driver/DriverLayout";
import DeliveryMap from "@/components/driver/DeliveryMap";
import { completeOrder, getDriverState, sendDriverLocation, startOrder } from "@/services/driverApi";

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
  const locationTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setCustomerLat(null);
    setCustomerLng(null);
    setStatus("DRIVER_ASSIGNED");
  }, [orderId]);

  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const state = await getDriverState();
        if (state.active_delivery?.id === orderId) {
          setStatus(state.active_delivery.status);
          setCustomerLat(state.active_delivery.customer_lat ?? null);
          setCustomerLng(state.active_delivery.customer_lng ?? null);
        } else {
          setCustomerLat(null);
          setCustomerLng(null);
        }
      } catch {
        setFeedback("Backend unavailable");
      }
    }, 2000);

    const stopLocationPolling = () => {
      if (locationTimerRef.current) {
        clearInterval(locationTimerRef.current);
        locationTimerRef.current = null;
      }
    };

    const sendCurrentLocation = () => {
      if (!navigator.geolocation || geoBlocked) return;
      navigator.geolocation.getCurrentPosition(
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
            stopLocationPolling();
            return;
          }

          setFeedback("Unable to read your location");
          stopLocationPolling();
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 0,
        },
      );
    };

    if (!navigator.geolocation) {
      setGeoBlocked(true);
      setFeedback("Geolocation not supported on this device");
    } else {
      sendCurrentLocation();
      locationTimerRef.current = setInterval(sendCurrentLocation, 5000);
    }

    return () => {
      clearInterval(timer);
      stopLocationPolling();
    };
  }, [geoBlocked, orderId]);

  return (
    <DriverLayout title={`Delivery #${orderId}`}>
      <p className="mb-2 text-sm">Current status: <strong>{status}</strong></p>
      <div className="mb-3 space-y-2">
        <button className="w-full rounded bg-amber-600 p-3 text-white" onClick={async () => {
          await startOrder(orderId);
          setStatus("OUT_FOR_DELIVERY");
          setFeedback("Delivery started");
        }}>START DELIVERY</button>
        <button className="w-full rounded bg-green-700 p-3 text-white" onClick={async () => {
          await completeOrder(orderId);
          setStatus("DELIVERED");
          setFeedback("Delivery completed");
        }}>COMPLETE DELIVERY</button>
      </div>
      <DeliveryMap
        orderId={orderId}
        driverLat={driverLat}
        driverLng={driverLng}
        customerLat={customerLat}
        customerLng={customerLng}
      />
      {feedback && <p className="mt-3 rounded bg-blue-50 p-2 text-sm text-blue-700">{feedback}</p>}
    </DriverLayout>
  );
}
