"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Coordinate = {
  lat?: number | null;
  lng?: number | null;
} | null;

type DeliveryProgressBarProps = {
  status: string | null | undefined;
  statusStep?: number | null;
  progress?: number | null;
  distanceMeters?: number | null;
  durationSeconds?: number | null;
  initialDistanceMeters?: number | null;
  currentLocation?: Coordinate;
  destinationLocation?: Coordinate;
  liveUpdatesEnabled?: boolean;
  isOffline?: boolean;
};

const MAX_STEP = 5;
const GOOGLE_MAPS_SCRIPT_ID = "google-maps-js";
const GOOGLE_MAPS_API_KEY = "AIzaSyCDi9WNbfW843u-GyJy4RNYWQ_2VDTrQiY";

declare global {
  interface Window {
    google?: any;
    __googleMapsScriptLoadingPromise?: Promise<void>;
  }
}

function loadGoogleMapsAssets() {
  if (typeof window === "undefined") {
    return Promise.resolve();
  }

  if (window.google?.maps) {
    return Promise.resolve();
  }

  if (window.__googleMapsScriptLoadingPromise) {
    return window.__googleMapsScriptLoadingPromise;
  }

  window.__googleMapsScriptLoadingPromise = new Promise<void>((resolve, reject) => {
    const existingScript = document.getElementById(GOOGLE_MAPS_SCRIPT_ID) as HTMLScriptElement | null;
    if (existingScript) {
      if (window.google?.maps) {
        resolve();
        return;
      }

      existingScript.addEventListener("load", () => resolve(), { once: true });
      existingScript.addEventListener("error", () => reject(new Error("Failed to load Google Maps")), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.id = GOOGLE_MAPS_SCRIPT_ID;
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(GOOGLE_MAPS_API_KEY)}`;
    script.async = true;
    script.defer = true;
    script.onload = () => {
      if (window.google?.maps) {
        resolve();
      }
    };
    script.onerror = () => reject(new Error("Failed to load Google Maps"));
    document.body.appendChild(script);
  });

  return window.__googleMapsScriptLoadingPromise;
}

function getStatus(status: string | null | undefined) {
  switch (String(status || "").trim().toLowerCase()) {
    case "pending":
      return "Aguardando cozinha";
    case "preparing":
      return "Em preparo";
    case "ready":
      return "Pronto";
    case "out_for_delivery":
    case "delivering":
      return "Saiu para entrega 🚀";
    case "delivered":
      return "Entregue 🎉";
    case "canceled":
      return "Pedido cancelado";
    default:
      return "Processando...";
  }
}

function isPresentNumber(value: number | null | undefined): value is number {
  return value !== null && value !== undefined && Number.isFinite(Number(value));
}

function formatDistanceLabel(distanceMeters: number | null | undefined) {
  if (!isPresentNumber(distanceMeters)) {
    return null;
  }

  return `${(Number(distanceMeters) / 1000).toFixed(2)} km`;
}

function formatEtaLabel(durationSeconds: number | null | undefined) {
  if (!isPresentNumber(durationSeconds)) {
    return null;
  }

  return `${Math.max(1, Math.round(Number(durationSeconds) / 60))} min`;
}

function normalizeCoordinate(point: Coordinate | undefined) {
  if (!point) {
    return null;
  }

  const lat = Number(point.lat);
  const lng = Number(point.lng);

  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return null;
  }

  return { lat, lng };
}

export default function DeliveryProgressBar({
  status,
  statusStep,
  progress,
  distanceMeters,
  durationSeconds,
  initialDistanceMeters,
  currentLocation,
  destinationLocation,
  liveUpdatesEnabled = true,
  isOffline = false,
}: DeliveryProgressBarProps) {
  const normalizedStatus = String(status || "").trim().toLowerCase();
  const safeStep = Math.max(0, Math.min(MAX_STEP, Number(statusStep || 0)));
  const isOutForDelivery = normalizedStatus === "out_for_delivery" || normalizedStatus === "delivering";
  const isDelivered = normalizedStatus === "delivered" || safeStep >= MAX_STEP;
  const isCanceled = normalizedStatus === "canceled";
  const [isCalculating, setIsCalculating] = useState(isOutForDelivery);
  const [routeDistanceMeters, setRouteDistanceMeters] = useState<number | null>(distanceMeters ?? null);
  const [routeDurationSeconds, setRouteDurationSeconds] = useState<number | null>(durationSeconds ?? null);
  const [routeProgress, setRouteProgress] = useState<number | null>(
    Number.isFinite(Number(progress)) ? Math.max(0, Math.min(1, Number(progress))) : null,
  );
  const lastValidDistanceMetersRef = useRef<number | null>(distanceMeters ?? null);
  const lastValidDurationSecondsRef = useRef<number | null>(durationSeconds ?? null);
  const lastValidProgressRef = useRef<number | null>(Number.isFinite(Number(progress)) ? Math.max(0, Math.min(1, Number(progress))) : null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    if (isPresentNumber(distanceMeters)) {
      lastValidDistanceMetersRef.current = distanceMeters;
      setRouteDistanceMeters(distanceMeters);
    }
  }, [distanceMeters]);

  useEffect(() => {
    if (isPresentNumber(durationSeconds)) {
      lastValidDurationSecondsRef.current = durationSeconds;
      setRouteDurationSeconds(durationSeconds);
    }
  }, [durationSeconds]);

  useEffect(() => {
    if (Number.isFinite(Number(progress))) {
      const normalizedProgress = Math.max(0, Math.min(1, Number(progress)));
      lastValidProgressRef.current = normalizedProgress;
      setRouteProgress(normalizedProgress);
    }
  }, [progress]);

  const normalizedCurrentLocation = useMemo(() => normalizeCoordinate(currentLocation), [currentLocation]);
  const normalizedDestinationLocation = useMemo(() => normalizeCoordinate(destinationLocation), [destinationLocation]);

  useEffect(() => {
    if (!isOutForDelivery || isDelivered || isCanceled) {
      setIsCalculating(false);
      return;
    }

    setIsCalculating(true);

    void loadGoogleMapsAssets()
      .then(() => {
        if (!window.google || !window.google.maps) {
          return;
        }

        setIsCalculating(false);
      })
      .catch((error) => {
        console.error("Failed to load Google Maps for tracking route", error);
        setIsCalculating(false);
      });
  }, [isCanceled, isDelivered, isOutForDelivery]);

  useEffect(() => {
    if (!isOutForDelivery || isDelivered || isCanceled) {
      return;
    }

    const calculateRoute = () => {
      if (!window.google || !window.google.maps) return;
      if (!normalizedCurrentLocation || !normalizedDestinationLocation) return;

      const currentRequestId = requestIdRef.current + 1;
      requestIdRef.current = currentRequestId;
      setIsCalculating(true);

      const directionsService = new window.google.maps.DirectionsService();
      directionsService.route(
        {
          origin: normalizedCurrentLocation,
          destination: normalizedDestinationLocation,
          travelMode: window.google.maps.TravelMode.DRIVING,
        },
        (result: any, status: string) => {
          if (currentRequestId !== requestIdRef.current) {
            return;
          }

          if (status === "OK" && result?.routes?.length > 0) {
            const leg = result.routes[0]?.legs?.[0];

            if (!leg?.distance?.value || !leg?.duration?.value) {
              setIsCalculating(false);
              return;
            }

            const nextDistanceMeters = Number(leg.distance.value);
            const nextDurationSeconds = Number(leg.duration.value);
            const distanceKm = nextDistanceMeters / 1000;
            const durationMin = Math.round(nextDurationSeconds / 60);

            const baselineDistance = Number(initialDistanceMeters);
            const totalDistance = Number.isFinite(baselineDistance) && baselineDistance > 0 ? baselineDistance : nextDistanceMeters;
            const remainingDistance = nextDistanceMeters;

            const nextProgress = Math.max(
              0,
              Math.min(100, ((totalDistance - remainingDistance) / totalDistance) * 100),
            ) / 100;

            setRouteDistanceMeters(nextDistanceMeters);
            setRouteDurationSeconds(nextDurationSeconds);
            setRouteProgress(nextProgress);
            lastValidDistanceMetersRef.current = nextDistanceMeters;
            lastValidDurationSecondsRef.current = nextDurationSeconds;
            lastValidProgressRef.current = nextProgress;
            setIsCalculating(false);

            console.log("Route result:", {
              distanceKm,
              durationMin,
            });
          } else {
            console.error("Directions failed", status);
            setRouteDistanceMeters((previous) => previous ?? lastValidDistanceMetersRef.current);
            setRouteDurationSeconds((previous) => previous ?? lastValidDurationSecondsRef.current);
            setRouteProgress((previous) => previous ?? lastValidProgressRef.current);
            setIsCalculating(false);
          }
        },
      );
    };

    calculateRoute();
  }, [currentLocation, initialDistanceMeters, isCanceled, isDelivered, isOutForDelivery, normalizedCurrentLocation, normalizedDestinationLocation]);

  const liveProgress = useMemo(() => {
    if (isDelivered) return 1;
    if (isCanceled || !isOutForDelivery) return 0;

    if (Number.isFinite(Number(routeProgress))) {
      return Math.max(0, Math.min(1, Number(routeProgress)));
    }

    const baselineDistance = Number(initialDistanceMeters);
    const currentDistance = Number(routeDistanceMeters);

    if (Number.isFinite(baselineDistance) && Number.isFinite(currentDistance) && baselineDistance > 0) {
      return Math.max(0, Math.min(1, 1 - currentDistance / baselineDistance));
    }

    if (Number.isFinite(Number(progress))) {
      return Math.max(0, Math.min(1, Number(progress)));
    }

    return 0;
  }, [initialDistanceMeters, isCanceled, isDelivered, isOutForDelivery, progress, routeDistanceMeters, routeProgress]);

  const formattedDistance = isOutForDelivery ? formatDistanceLabel(routeDistanceMeters) : null;
  const formattedEta = isOutForDelivery ? formatEtaLabel(routeDurationSeconds) : null;
  const statusLabel = getStatus(normalizedStatus);
  const etaMetricLabel = isOffline ? "Sem atualização" : formattedEta || (isDelivered ? "Concluído" : isCalculating ? "Calculando rota..." : "Rota indisponível");
  const shouldShowRouteCalculation = isOutForDelivery && isCalculating && !formattedDistance && !formattedEta;

  if (!status && safeStep <= 0) {
    return <div>Carregando rastreamento...</div>;
  }

  if (isCanceled || !isOutForDelivery) {
    return null;
  }

  return (
    <div className="tracking-shell flex w-full flex-col gap-4 rounded-[28px] border border-slate-200/80 bg-white/95 p-4 shadow-[0_18px_50px_rgba(15,23,42,0.08)] backdrop-blur sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Rastreamento premium</p>
          <h2 className="mt-1 text-base font-semibold text-slate-900 sm:text-lg">{statusLabel}</h2>
          {formattedDistance || formattedEta ? (
            <p className="mt-1 text-xs text-slate-500 sm:text-sm">
              {[formattedDistance, formattedEta ? `ETA ${formattedEta}` : null].filter(Boolean).join(" • ")}
            </p>
          ) : shouldShowRouteCalculation ? (
            <p className="mt-1 text-xs text-slate-500 sm:text-sm">Calculando rota...</p>
          ) : null}
          <p className="mt-1 text-xs text-slate-500 sm:text-sm">
            {isOffline ? "Entregador offline" : liveUpdatesEnabled ? "Atualizando em tempo real" : "Sem atualização recente"}
          </p>
        </div>

        <div className="live-indicator shrink-0">
          <span className="dot" />
          {isOffline ? "Entregador offline" : liveUpdatesEnabled ? "Atualizando em tempo real" : "Sem atualização recente"}
        </div>
      </div>

      <div className="track-stage relative pb-5 pt-8">
        <div className="track-base" aria-hidden="true" />
        <div className="progress-fill" style={{ width: `${liveProgress * 100}%` }} aria-hidden="true" />

        <div className="live-dot" style={{ left: `${liveProgress * 100}%`, transform: "translateX(-50%)" }} aria-hidden="true" />

        <div
          className="motorcycle"
          style={{
            left: `${liveProgress * 100}%`,
            transform: "translateX(-50%)",
          }}
          aria-hidden="true"
        >
          <span className={`motorcycle-icon ${isDelivered ? "arrived" : ""}`}>🏍️</span>
        </div>

        <div className={`destination ${isDelivered ? "arrived" : ""}`} aria-hidden="true">
          🏠
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs sm:text-sm">
        <div className="metric-card">
          <span className="metric-label">Progresso</span>
          <span className="metric-value">{Math.round(liveProgress * 100)}%</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Previsão</span>
          <span className="metric-value">{etaMetricLabel}</span>
        </div>
      </div>

      <style jsx>{`
        .tracking-shell { overflow: hidden; opacity: 0; animation: fadeIn 0.35s ease forwards; }
        .track-stage { overflow: visible; padding-left: 24px; padding-right: 24px; }
        .track-base { position: absolute; inset: 50% 24px auto 24px; height: 6px; transform: translateY(-50%); border-radius: 999px; background: linear-gradient(90deg, rgba(226, 232, 240, 0.9), rgba(203, 213, 225, 0.9)); }
        .progress-fill { position: absolute; inset: 50% auto auto 24px; height: 6px; transform: translateY(-50%); border-radius: 999px; background: linear-gradient(90deg, #facc15, #22c55e); transition: width 0.5s linear; box-shadow: 0 0 24px rgba(34, 197, 94, 0.35); will-change: width; }
        .motorcycle { position: absolute; top: -12px; transition: left 0.4s ease-out; font-size: 1.65rem; filter: drop-shadow(0 8px 16px rgba(15, 23, 42, 0.18)); will-change: left; z-index: 3; }
        .motorcycle-icon { display: inline-flex; animation: subtleShake 2s infinite; transform-origin: center; }
        .live-dot { width: 10px; height: 10px; background: #22c55e; border-radius: 50%; position: absolute; top: 50%; animation: pulse 1.5s infinite; box-shadow: 0 0 0 6px rgba(34, 197, 94, 0.14); transition: left 0.4s ease-out; z-index: 2; }
        .destination { position: absolute; right: 24px; top: -12px; font-size: 1.55rem; filter: drop-shadow(0 8px 16px rgba(15, 23, 42, 0.14)); }
        .motorcycle-icon.arrived { animation: arriveMotorcycle 0.6s ease; }
        .destination.arrived { animation: arrive 0.6s ease; }
        .live-indicator { font-size: 12px; color: #16a34a; display: flex; align-items: center; gap: 6px; border-radius: 999px; background: rgba(34, 197, 94, 0.08); padding: 8px 10px; white-space: nowrap; }
        .dot { width: 6px; height: 6px; background: #16a34a; border-radius: 50%; animation: pulseDot 1s infinite; }
        .metric-card { display: flex; flex-direction: column; gap: 4px; border-radius: 18px; border: 1px solid rgba(226, 232, 240, 0.9); background: linear-gradient(180deg, rgba(248, 250, 252, 0.95), rgba(241, 245, 249, 0.85)); padding: 12px 14px; }
        .metric-label { color: #64748b; }
        .metric-value { color: #0f172a; font-weight: 600; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.6); opacity: 0.5; } 100% { transform: scale(1); opacity: 1; } }
        @keyframes pulseDot { 0% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.4); opacity: 0.55; } 100% { transform: scale(1); opacity: 1; } }
        @keyframes subtleShake { 0%, 100% { transform: rotate(0deg); } 50% { transform: rotate(1deg); } }
        @keyframes arriveMotorcycle { 0% { transform: translateX(-50%) scale(1); } 50% { transform: translateX(-50%) scale(1.1); } 100% { transform: translateX(-50%) scale(1); } }
        @keyframes arrive { 0% { transform: scale(1); } 50% { transform: scale(1.08); } 100% { transform: scale(1); } }
      `}</style>
    </div>
  );
}
