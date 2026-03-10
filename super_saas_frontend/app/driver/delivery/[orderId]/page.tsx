"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import DriverLayout from "@/components/driver/DriverLayout";
import DeliveryMap from "@/components/driver/DeliveryMap";
import { completeOrder, getDriverState, sendDriverLocation, startOrder } from "@/services/driverApi";

export default function DriverDeliveryPage() {
  const params = useParams<{ orderId: string }>();
  const orderId = Number(params.orderId);
  const [status, setStatus] = useState("DRIVER_ASSIGNED");
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const state = await getDriverState();
        if (state.active_delivery) setStatus(state.active_delivery.status);
      } catch {
        setFeedback("Backend unavailable");
      }
    }, 2000);

    const locationTimer = setInterval(() => {
      if (!navigator.geolocation) return;
      navigator.geolocation.getCurrentPosition((position) => {
        sendDriverLocation({
          order_id: orderId,
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        }).catch(() => setFeedback("Location update failed"));
      });
    }, 5000);

    return () => {
      clearInterval(timer);
      clearInterval(locationTimer);
    };
  }, [orderId]);

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
      <a className="mb-3 block rounded border p-3 text-center" href={`https://www.google.com/maps/search/?api=1&query=customer+address`} target="_blank">OPEN NAVIGATION</a>
      <DeliveryMap />
      {feedback && <p className="mt-3 rounded bg-blue-50 p-2 text-sm text-blue-700">{feedback}</p>}
    </DriverLayout>
  );
}
