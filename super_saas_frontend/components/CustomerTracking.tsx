"use client";

import { useEffect, useMemo, useState } from "react";

import TrackingMap from "@/components/tracking/TrackingMap";
import { storefrontFetch } from "@/lib/storefrontApi";
import { normalizeTrackingStatus } from "@/lib/orderTrackingStatus";
import { isFiniteTrackingNumber as isValidCoordinate, formatTrackingEta as formatEta } from "@/lib/trackingPresentation";

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
  status?: string | null;
  destinationLocation?: LatLng | null;
} | null;

type CustomerTrackingProps = {
  order: CustomerTrackingOrder;
  trackingToken: string;
  tracking?: CustomerTrackingState;
};

type DriverLocationResponse = {
  lat?: number;
  lng?: number;
  driver_lat?: number | null;
  driver_lng?: number | null;
  destination_lat?: number | null;
  destination_lng?: number | null;
};

const LOCATION_POLLING_INTERVAL_MS = 2_000;

export default function CustomerTracking({ order, trackingToken, tracking }: CustomerTrackingProps) {
  const [polledTrackingState, setPolledTrackingState] = useState<{
    driverPosition: LatLng | null;
    destination: LatLng | null;
  }>({ driverPosition: null, destination: null });

  const normalizedStatus = normalizeTrackingStatus(order?.status ?? "");
  const isOutForDelivery = normalizedStatus === "delivering";
  const destinationLat = tracking?.destinationLat ?? order?.destinationLocation?.lat ?? null;
  const destinationLng = tracking?.destinationLng ?? order?.destinationLocation?.lng ?? null;
  const resolvedDestination =
    isValidCoordinate(destinationLat) && isValidCoordinate(destinationLng)
      ? { lat: Number(destinationLat), lng: Number(destinationLng) }
      : null;

  useEffect(() => {
    if (!isOutForDelivery || !trackingToken) {
      setPolledTrackingState({ driverPosition: null, destination: null });
      return;
    }

    let cancelled = false;

    const fetchDriverLocation = async () => {
      try {
        const response = await storefrontFetch(`/public/order/${encodeURIComponent(trackingToken)}`, {
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

        const driverLat = payload.driver_lat ?? payload.lat;
        const driverLng = payload.driver_lng ?? payload.lng;
        setPolledTrackingState({
          driverPosition:
            isValidCoordinate(driverLat) && isValidCoordinate(driverLng)
              ? { lat: driverLat, lng: driverLng }
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
  }, [isOutForDelivery, trackingToken]);

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

  const etaLabel = isOutForDelivery && liveDriverPosition
    ? formatEta(tracking?.durationSeconds, tracking?.distanceMeters)
    : null;
  const helperMessage = normalizedStatus === "delivered"
    ? "Pedido entregue. Bom apetite!"
    : normalizedStatus === "canceled"
      ? "Pedido cancelado."
      : isOutForDelivery
        ? liveDriverPosition
          ? "Seu pedido saiu para entrega. Acompanhe a posição recebida do entregador."
          : "Seu pedido saiu para entrega. Aguardando o GPS do entregador."
        : normalizedStatus === "ready"
          ? "Pedido pronto. Aguardando a saída para entrega."
          : "Seu pedido está na cozinha. Avisaremos quando sair para entrega.";

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
