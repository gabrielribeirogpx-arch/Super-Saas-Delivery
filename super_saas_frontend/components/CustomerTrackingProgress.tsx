"use client";

import DeliveryProgressBar from "@/components/tracking/DeliveryProgressBar";

type CustomerTrackingState = {
  driverLat?: number | null;
  driverLng?: number | null;
  distanceMeters?: number | null;
  durationSeconds?: number | null;
  progress?: number | null;
} | null;

type CustomerTrackingOrder = {
  status?: string | null;
  status_step?: number | null;
  progress?: number | null;
  distance_meters?: number | null;
  duration_seconds?: number | null;
  initial_distance_meters?: number | null;
  liveUpdatesEnabled?: boolean;
  isOffline?: boolean;
} | null;

type CustomerTrackingProgressProps = {
  order: CustomerTrackingOrder;
  tracking?: CustomerTrackingState;
};

export default function CustomerTrackingProgress({ order, tracking }: CustomerTrackingProgressProps) {
  if (!order) {
    return <div className="rounded-xl border border-slate-200 p-4 text-center text-sm text-slate-500">Carregando rastreamento do pedido...</div>;
  }

  const normalizedStatus = order.status?.toUpperCase().trim();
  const isOutForDelivery = normalizedStatus === "OUT_FOR_DELIVERY" || normalizedStatus === "DELIVERING";

  console.log("Tracking UI Debug:", {
    status: order.status,
    trackingDistanceMeters: tracking?.distanceMeters,
    trackingDurationSeconds: tracking?.durationSeconds,
  });

  if (!isOutForDelivery) {
    return null;
  }

  return (
    <DeliveryProgressBar
      status={order.status}
      statusStep={order.status_step}
      progress={tracking?.progress ?? order.progress ?? 0}
      distanceMeters={tracking?.distanceMeters}
      durationSeconds={tracking?.durationSeconds}
      initialDistanceMeters={order.initial_distance_meters}
      liveUpdatesEnabled={order.liveUpdatesEnabled}
      isOffline={order.isOffline}
    />
  );
}
