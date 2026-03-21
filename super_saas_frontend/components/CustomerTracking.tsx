"use client";

import { useEffect, useMemo, useState } from "react";

import TrackingMap from "@/components/tracking/TrackingMap";
import { storefrontFetch } from "@/lib/storefrontApi";

type CustomerTrackingState = {
  destinationLat?: number | null;
  destinationLng?: number | null;
  driverLat?: number | null;
  driverLng?: number | null;
  hasDriverLocation?: boolean;
  distanceMeters?: number | null;
  durationSeconds?: number | null;
} | null;

type LatLng = { lat: number; lng: number };

type CustomerTrackingOrder = {
  id?: number | string | null;
  order_id?: number | string | null;
  status?: string | null;
  destinationLocation?: LatLng | null;
} | null;

type CustomerTrackingProps = {
  order: CustomerTrackingOrder;
  tracking?: CustomerTrackingState;
};

type DriverLocationResponse = {
  lat?: number;
  lng?: number;
  destination_lat?: number | null;
  destination_lng?: number | null;
};

const LOCATION_POLLING_INTERVAL_MS = 2_000;

function isValidCoordinate(value: unknown): value is number {
  return Number.isFinite(Number(value));
}

function formatEta(durationSeconds?: number | null, distanceMeters?: number | null) {
  if (!isValidCoordinate(durationSeconds) && !isValidCoordinate(distanceMeters)) {
    return null;
  }

  const parts: string[] = [];

  if (isValidCoordinate(durationSeconds)) {
    const minutes = Math.max(1, Math.round(Number(durationSeconds) / 60));
    parts.push(`Chegando em ${minutes} min`);
  }

  if (isValidCoordinate(distanceMeters)) {
    const kilometers = Number(distanceMeters) / 1000;
    parts.push(`${kilometers.toFixed(kilometers >= 10 ? 0 : 1)} km`);
  }

  return parts.join(" • ");
}

export default function CustomerTracking({ order, tracking }: CustomerTrackingProps) {
  const [polledTrackingState, setPolledTrackingState] = useState<{
    driverPosition: LatLng | null;
    destination: LatLng | null;
  }>({ driverPosition: null, destination: null });

  const normalizedStatus = order?.status?.toUpperCase().trim();
  const isOutForDelivery = normalizedStatus === "OUT_FOR_DELIVERY";
  const orderId = order?.order_id ?? order?.id ?? null;
  const destinationLat = tracking?.destinationLat ?? order?.destinationLocation?.lat ?? null;
  const destinationLng = tracking?.destinationLng ?? order?.destinationLocation?.lng ?? null;
  const resolvedDestination =
    isValidCoordinate(destinationLat) && isValidCoordinate(destinationLng)
      ? { lat: Number(destinationLat), lng: Number(destinationLng) }
      : null;

  useEffect(() => {
    if (!isOutForDelivery || orderId == null) {
      setPolledTrackingState({ driverPosition: null, destination: null });
      return;
    }

    let cancelled = false;

    const fetchDriverLocation = async () => {
      try {
        const response = await storefrontFetch(`/location/${encodeURIComponent(String(orderId))}`, {
          cache: "no-store",
          headers: {
            "Cache-Control": "no-cache",
            Pragma: "no-cache",
          },
        });

        if (!response.ok) {
          return;
        }

        const payload = (await response.json()) as DriverLocationResponse;
        if (cancelled) {
          return;
        }

        setPolledTrackingState({
          driverPosition:
            isValidCoordinate(payload.lat) && isValidCoordinate(payload.lng)
              ? { lat: Number(payload.lat), lng: Number(payload.lng) }
              : null,
          destination:
            isValidCoordinate(payload.destination_lat) && isValidCoordinate(payload.destination_lng)
              ? { lat: Number(payload.destination_lat), lng: Number(payload.destination_lng) }
              : null,
        });
      } catch {
        // Keep the last known marker position when polling fails.
      }
    };

    void fetchDriverLocation();
    const intervalId = window.setInterval(() => {
      void fetchDriverLocation();
    }, LOCATION_POLLING_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [isOutForDelivery, orderId]);

  const liveDriverPosition = useMemo(() => {
    if (polledTrackingState.driverPosition) {
      return polledTrackingState.driverPosition;
    }

    if (isValidCoordinate(tracking?.driverLat) && isValidCoordinate(tracking?.driverLng)) {
      return {
        lat: Number(tracking?.driverLat),
        lng: Number(tracking?.driverLng),
      };
    }

    return null;
  }, [polledTrackingState.driverPosition, tracking?.driverLat, tracking?.driverLng]);

  const liveDestination = polledTrackingState.destination ?? resolvedDestination;

  const etaLabel = formatEta(tracking?.durationSeconds, tracking?.distanceMeters);
  const helperMessage = isOutForDelivery
    ? "🚀 Seu pedido saiu para entrega — acompanhe em tempo real"
    : "Seu pedido ainda está sendo preparado";

  if (!order) {
    return <div className="rounded-xl border border-slate-200 p-4 text-center text-sm text-slate-500">Carregando rastreamento do pedido...</div>;
  }

  return (
    <div className="space-y-3">
      {etaLabel ? <p className="text-sm font-medium text-slate-700">{etaLabel}</p> : null}
      <p className="text-sm text-slate-500">{helperMessage}</p>
      <TrackingMap
        isOutForDelivery={isOutForDelivery}
        tracking={{
          destinationLat: liveDestination?.lat ?? resolvedDestination?.lat ?? null,
          destinationLng: liveDestination?.lng ?? resolvedDestination?.lng ?? null,
          driverLat: liveDriverPosition?.lat ?? null,
          driverLng: liveDriverPosition?.lng ?? null,
          hasDriverLocation: Boolean(liveDriverPosition),
        }}
        destination={liveDestination}
      />
    </div>
  );
}
