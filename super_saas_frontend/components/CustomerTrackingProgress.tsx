"use client";

import { useMemo } from "react";

import DeliveryProgressBar from "@/components/tracking/DeliveryProgressBar";
import TrackingMap from "@/components/tracking/TrackingMap";

type CustomerTrackingState = {
  driverLat?: number | null;
  driverLng?: number | null;
  distanceMeters?: number | null;
  durationSeconds?: number | null;
  progress?: number | null;
} | null;

type LatLng = { lat: number; lng: number };

type CustomerTrackingOrder = {
  status?: string | null;
  status_step?: number | null;
  destinationLocation?: LatLng | null;
  distance_meters?: number | null;
  duration_seconds?: number | null;
  progress?: number | null;
  initial_distance_meters?: number | null;
  liveUpdatesEnabled?: boolean;
  isOffline?: boolean;
} | null;

type CustomerTrackingProgressProps = {
  order: CustomerTrackingOrder;
  tracking?: CustomerTrackingState;
};

const AVERAGE_SPEED_KMH = 30;
const AVERAGE_SPEED_METERS_PER_SECOND = (AVERAGE_SPEED_KMH * 1000) / 3600;

function isFiniteCoordinate(value: unknown): value is number {
  return Number.isFinite(Number(value));
}

function calculateDistance(lat1: number, lng1: number, lat2: number, lng2: number) {
  const toRadians = (degrees: number) => (degrees * Math.PI) / 180;
  const earthRadiusMeters = 6_371_000;
  const deltaLat = toRadians(lat2 - lat1);
  const deltaLng = toRadians(lng2 - lng1);
  const a =
    Math.sin(deltaLat / 2) ** 2
    + Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(deltaLng / 2) ** 2;

  return earthRadiusMeters * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)));
}

export default function CustomerTrackingProgress({ order, tracking }: CustomerTrackingProgressProps) {
  const normalizedStatus = order?.status?.toUpperCase().trim();
  const isOutForDelivery = normalizedStatus === "OUT_FOR_DELIVERY" || normalizedStatus === "DELIVERING";

  const resolvedMetrics = useMemo(() => {
    const driverLat = tracking?.driverLat;
    const driverLng = tracking?.driverLng;
    const destination = order?.destinationLocation;
    const sseDistance = tracking?.distanceMeters ?? order?.distance_meters ?? null;
    const sseDuration = tracking?.durationSeconds ?? order?.duration_seconds ?? null;
    const fallbackDistance =
      isFiniteCoordinate(driverLat)
      && isFiniteCoordinate(driverLng)
      && destination
      && isFiniteCoordinate(destination.lat)
      && isFiniteCoordinate(destination.lng)
        ? Math.round(calculateDistance(Number(driverLat), Number(driverLng), destination.lat, destination.lng))
        : null;

    const distanceMeters = sseDistance ?? fallbackDistance;
    const durationSeconds = sseDuration ?? (fallbackDistance != null ? Math.max(60, Math.round(fallbackDistance / AVERAGE_SPEED_METERS_PER_SECOND)) : null);
    const baselineDistance = order?.initial_distance_meters ?? order?.distance_meters ?? tracking?.distanceMeters ?? fallbackDistance ?? null;
    const progress =
      tracking?.progress
      ?? order?.progress
      ?? (baselineDistance != null && distanceMeters != null && baselineDistance > 0
        ? Math.max(0, Math.min(1, 1 - distanceMeters / baselineDistance))
        : null);

    return { distanceMeters, durationSeconds, progress, baselineDistance };
  }, [order, tracking]);

  if (!order) {
    return <div className="rounded-xl border border-slate-200 p-4 text-center text-sm text-slate-500">Carregando rastreamento do pedido...</div>;
  }

  if (!isOutForDelivery) {
    return null;
  }

  return (
    <div className="space-y-4">
      <DeliveryProgressBar
        status={order.status}
        statusStep={order.status_step}
        progress={resolvedMetrics.progress}
        distanceMeters={resolvedMetrics.distanceMeters}
        durationSeconds={resolvedMetrics.durationSeconds}
        initialDistanceMeters={resolvedMetrics.baselineDistance}
        liveUpdatesEnabled={order.liveUpdatesEnabled}
        isOffline={order.isOffline}
      />
      <TrackingMap tracking={{ ...tracking, ...resolvedMetrics }} destination={order.destinationLocation ?? null} />
    </div>
  );
}
