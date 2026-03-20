"use client";

import TrackingMap from "@/components/tracking/TrackingMap";

type CustomerTrackingState = {
  driverLat?: number | null;
  driverLng?: number | null;
} | null;

type LatLng = { lat: number; lng: number };

type CustomerTrackingOrder = {
  status?: string | null;
  destinationLocation?: LatLng | null;
} | null;

type CustomerTrackingProps = {
  order: CustomerTrackingOrder;
  tracking?: CustomerTrackingState;
};

export default function CustomerTracking({ order, tracking }: CustomerTrackingProps) {
  if (!order) {
    return <div className="rounded-xl border border-slate-200 p-4 text-center text-sm text-slate-500">Carregando rastreamento do pedido...</div>;
  }

  const normalizedStatus = order.status?.toUpperCase().trim();

  if (normalizedStatus !== "OUT_FOR_DELIVERY") {
    return null;
  }

  const hasDriverCoordinates = tracking?.driverLat !== null
    && tracking?.driverLat !== undefined
    && tracking?.driverLng !== null
    && tracking?.driverLng !== undefined;

  if (!hasDriverCoordinates) {
    return null;
  }

  return <TrackingMap tracking={tracking ?? null} destination={order.destinationLocation ?? null} />;
}
