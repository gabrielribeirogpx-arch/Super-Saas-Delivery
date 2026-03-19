"use client";

import DeliveryProgressBar from "@/components/tracking/DeliveryProgressBar";

type Coordinate = {
  lat?: number | null;
  lng?: number | null;
} | null;

type CustomerTrackingOrder = {
  status?: string | null;
  status_step?: number | null;
  progress?: number | null;
  distance_km?: number | null;
  eta_seconds?: number | null;
  last_location?: Coordinate;
  destinationLocation?: Coordinate;
  liveUpdatesEnabled?: boolean;
  isOffline?: boolean;
} | null;

type CustomerTrackingProgressProps = {
  order: CustomerTrackingOrder;
  driverLocation?: Coordinate;
};

export default function CustomerTrackingProgress({ order, driverLocation }: CustomerTrackingProgressProps) {
  if (!order) {
    return <div className="rounded-xl border border-slate-200 p-4 text-center text-sm text-slate-500">Carregando rastreamento do pedido...</div>;
  }

  const isOutForDelivery = order.status?.toUpperCase().trim() === "OUT_FOR_DELIVERY";

  console.log("Tracking UI Debug:", {
    status: order.status,
    driverLocation,
  });

  if (!isOutForDelivery) {
    return null;
  }

  return (
    <DeliveryProgressBar
      status={order.status}
      statusStep={order.status_step}
      progress={order.progress ?? 0}
      distanceKm={order.distance_km}
      etaSeconds={order.eta_seconds}
      currentLocation={driverLocation ?? order.last_location}
      destinationLocation={order.destinationLocation}
      liveUpdatesEnabled={order.liveUpdatesEnabled}
      isOffline={order.isOffline}
    />
  );
}
