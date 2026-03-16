"use client";

import { useEffect, useMemo, useState } from "react";

import CustomerTrackingMap from "@/components/maps/CustomerTrackingMap";

type TrackingOrder = {
  id?: number;
  order_id?: number;
  status?: string;
  customer_lat?: number | null;
  customer_lng?: number | null;
  driver_lat?: number | null;
  driver_lng?: number | null;
  last_location?: {
    lat?: number | null;
    lng?: number | null;
  } | null;
};

const GOOGLE_MAPS_API_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || "AIzaSyCDi9WNbfW843u-GyJy4RNYWQ_2VDTrQiY";

export default function TrackOrderPage({ params }: { params: { order_id: string } }) {
  const [order, setOrder] = useState<TrackingOrder | null>(null);

  useEffect(() => {
    let isMounted = true;

    const fetchOrder = async () => {
      try {
        const response = await fetch(`/api/delivery/orders/${params.order_id}`, {
          cache: "no-store",
          credentials: "include",
        });

        if (!response.ok) {
          return;
        }

        const payload = (await response.json()) as TrackingOrder;
        console.info("[tracking] fetched order status", {
          orderId: params.order_id,
          rawStatus: payload?.status,
        });

        if (isMounted) {
          setOrder(payload);
        }
      } catch {
        // silent tracking page failure
      }
    };

    void fetchOrder();
    const interval = setInterval(fetchOrder, 15000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [params.order_id]);

  const normalizedStatus = String(order?.status || "")
    .trim()
    .toUpperCase()
    .replace(/[-\s]+/g, "_");

  const isOutForDelivery =
    normalizedStatus === "OUT_FOR_DELIVERY" ||
    normalizedStatus === "SAIU_PARA_ENTREGA" ||
    normalizedStatus === "SAIU";

  const customerLocation = useMemo(() => {
    const lat = Number(order?.customer_lat);
    const lng = Number(order?.customer_lng);

    return {
      lat: Number.isFinite(lat) ? lat : -23.5505,
      lng: Number.isFinite(lng) ? lng : -46.6333,
    };
  }, [order?.customer_lat, order?.customer_lng]);

  const driverLocation = useMemo(() => {
    const lat = Number(order?.driver_lat ?? order?.last_location?.lat);
    const lng = Number(order?.driver_lng ?? order?.last_location?.lng);

    return {
      lat: Number.isFinite(lat) ? lat : customerLocation.lat,
      lng: Number.isFinite(lng) ? lng : customerLocation.lng,
    };
  }, [customerLocation.lat, customerLocation.lng, order?.driver_lat, order?.driver_lng, order?.last_location?.lat, order?.last_location?.lng]);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-2xl font-semibold">Delivery tracking</h1>
      <p className="text-sm text-slate-600">Order #{params.order_id}</p>

      {isOutForDelivery ? (
        <CustomerTrackingMap
          orderId={params.order_id}
          apiKey={GOOGLE_MAPS_API_KEY}
          customerLocation={customerLocation}
          driverLocation={driverLocation}
        />
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">Tracking map is available when order status is OUT_FOR_DELIVERY.</div>
      )}
    </main>
  );
}
