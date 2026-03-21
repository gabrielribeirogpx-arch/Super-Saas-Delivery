"use client";

import TrackingMap from "@/components/tracking/TrackingMap";

type CustomerTrackingState = {
  destinationLat?: number | null;
  destinationLng?: number | null;
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

  const destinationLat = tracking?.destinationLat ?? order.destinationLocation?.lat ?? null;
  const destinationLng = tracking?.destinationLng ?? order.destinationLocation?.lng ?? null;

  if (destinationLat == null || destinationLng == null) {
    return (
      <div className="rounded-xl border border-slate-200 p-4 text-center text-sm text-slate-500">
        Endereço do cliente não disponível
      </div>
    );
  }

  return (
    <TrackingMap
      tracking={{
        destinationLat,
        destinationLng,
        driverLat: tracking?.driverLat ?? null,
        driverLng: tracking?.driverLng ?? null,
      }}
      destination={{ lat: destinationLat, lng: destinationLng }}
    />
  );
}
