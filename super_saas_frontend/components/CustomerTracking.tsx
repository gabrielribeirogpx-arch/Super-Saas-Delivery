"use client";

import TrackingMap from "@/components/tracking/TrackingMap";
import { LoadingExperience } from "@/components/ui/loading-experience";
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
  tracking?: CustomerTrackingState;
};

export default function CustomerTracking({ order, tracking }: CustomerTrackingProps) {

  const normalizedStatus = normalizeTrackingStatus(order?.status ?? "");
  const isOutForDelivery = normalizedStatus === "delivering";
  const destinationLat = tracking?.destinationLat ?? order?.destinationLocation?.lat ?? null;
  const destinationLng = tracking?.destinationLng ?? order?.destinationLocation?.lng ?? null;
  const resolvedDestination =
    isValidCoordinate(destinationLat) && isValidCoordinate(destinationLng)
      ? { lat: Number(destinationLat), lng: Number(destinationLng) }
      : null;

  const liveDriverPosition: LatLng | null =
    isValidCoordinate(tracking?.driverLat) && isValidCoordinate(tracking?.driverLng)
      ? { lat: Number(tracking?.driverLat), lng: Number(tracking?.driverLng) }
      : null;

  const liveDestination = resolvedDestination;

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
    return <LoadingExperience variant="storefront" label="Atualizando a entrega" compact />;
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
