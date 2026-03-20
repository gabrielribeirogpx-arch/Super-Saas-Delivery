"use client";

import TrackingMap from "@/components/tracking/TrackingMap";

type CustomerTrackingState = {
  driverLat?: number | null;
  driverLng?: number | null;
  distanceMeters?: number | null;
  durationSeconds?: number | null;
  progress?: number | null;
} | null;

type CustomerTrackingOrder = {
  status?: string | null;
  destinationLocation?: { lat: number; lng: number } | null;
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

  if (!isOutForDelivery) {
    return null;
  }

  return <TrackingMap tracking={tracking} destination={order.destinationLocation ?? null} />;
}
