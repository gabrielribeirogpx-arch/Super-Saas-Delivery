"use client";

import CustomerTrackingMap from "@/components/maps/CustomerTrackingMap";

export default function TrackOrderPage({ params }: { params: { order_id: string } }) {
  const customerLocation = {
    lat: -23.5505,
    lng: -46.6333,
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-2xl font-semibold">Delivery tracking</h1>
      <p className="text-sm text-slate-600">Order #{params.order_id}</p>
      <p className="text-sm text-slate-500">Debug mode: rendering static map independent from API and SSE.</p>

      <CustomerTrackingMap
        orderId={params.order_id}
        customerLocation={customerLocation}
        driverLocation={null}
      />
    </main>
  );
}
