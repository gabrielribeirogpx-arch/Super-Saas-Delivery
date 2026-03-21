"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { TrackingAnimator } from "@/lib/maps/trackingAnimator";

type TrackingState = {
  destinationLat?: number | null;
  destinationLng?: number | null;
  driverLat?: number | null;
  driverLng?: number | null;
  hasDriverLocation?: boolean;
} | null;

type LatLngLiteral = {
  lat: number;
  lng: number;
};

type TrackingMapProps = {
  tracking: TrackingState;
  destination: LatLngLiteral | null;
  isOutForDelivery: boolean;
};

const GOOGLE_MAPS_SCRIPT_ID = "google-maps-js";
const GOOGLE_MAPS_API_KEY = "AIzaSyCDi9WNbfW843u-GyJy4RNYWQ_2VDTrQiY";
const FALLBACK_CENTER = { lat: -23.5505, lng: -46.6333 };
const DEFAULT_ZOOM = 16;
const MOTORCYCLE_ICON = {
  url:
    "data:image/svg+xml;charset=UTF-8," +
    encodeURIComponent(`
      <svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" viewBox="0 0 56 56" fill="none">
        <circle cx="28" cy="28" r="28" fill="#0F172A" fill-opacity="0.92"/>
        <path d="M17 33.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9Zm22 0a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9ZM27.4 18c-1.7 0-3.1 1.4-3.1 3.1 0 .9.4 1.8 1.1 2.4l-2 4h-5.6c-.8 0-1.4.6-1.4 1.4s.6 1.4 1.4 1.4h7.3c.5 0 1-.3 1.2-.8l1.6-3.3 2.5 2.2c.3.3.7.4 1.1.4h4.6l2.3 4.4c.2.4.6.7 1.1.8a7.3 7.3 0 0 1 4.4 2.7c.5.6 1.4.7 2 .2.6-.5.7-1.4.2-2a10 10 0 0 0-4.9-3.4l-3-5.8a1.4 1.4 0 0 0-1.2-.7h-4.9l-3.6-3.1a3.1 3.1 0 0 0 .9-2.2c0-1.7-1.4-3.1-3.1-3.1Z" fill="#F8FAFC"/>
      </svg>
    `),
  scaledSize: { width: 40, height: 40 },
  anchor: { x: 20, y: 20 },
};
const PLACEHOLDER_ICON = {
  url:
    "data:image/svg+xml;charset=UTF-8," +
    encodeURIComponent(`
      <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48" fill="none">
        <circle cx="24" cy="24" r="24" fill="#FFFFFF" fill-opacity="0.96"/>
        <path d="M24 11c-4.4 0-8 3.4-8 7.7 0 5.8 8 16.3 8 16.3s8-10.5 8-16.3c0-4.3-3.6-7.7-8-7.7Zm0 10.5a2.8 2.8 0 1 1 0-5.6 2.8 2.8 0 0 1 0 5.6Z" fill="#22C55E"/>
      </svg>
    `),
  scaledSize: { width: 36, height: 36 },
  anchor: { x: 18, y: 32 },
};

declare global {
  interface Window {
    google?: any;
    __googleMapsScriptLoadingPromise?: Promise<void>;
  }
}

function hasValidCoordinates(value: LatLngLiteral | null | undefined): value is LatLngLiteral {
  if (!value) {
    return false;
  }

  return Number.isFinite(value.lat) && Number.isFinite(value.lng) && Math.abs(value.lat) <= 90 && Math.abs(value.lng) <= 180;
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

export default function TrackingMap({ tracking, destination, isOutForDelivery }: TrackingMapProps) {
  const destinationLat = tracking?.destinationLat ?? destination?.lat ?? null;
  const destinationLng = tracking?.destinationLng ?? destination?.lng ?? null;
  const resolvedDestination = hasValidCoordinates(
    destinationLat != null && destinationLng != null
      ? { lat: Number(destinationLat), lng: Number(destinationLng) }
      : null,
  )
    ? { lat: Number(destinationLat), lng: Number(destinationLng) }
    : null;
  const fallbackMarkerPosition = resolvedDestination ?? FALLBACK_CENTER;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const driverMarkerRef = useRef<any>(null);
  const customerMarkerRef = useRef<any>(null);
  const routeLineRef = useRef<any>(null);
  const driverAnimatorRef = useRef<TrackingAnimator | null>(null);
  const lastDriverPositionRef = useRef<LatLngLiteral | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);

  const hasDriverLocation = tracking?.hasDriverLocation ?? false;
  const isDriverPositionLoading = isOutForDelivery && !hasDriverLocation;

  const driverPosition = useMemo<LatLngLiteral | null>(() => {
    if (!hasValidCoordinates(
      tracking?.driverLat != null && tracking?.driverLng != null
        ? { lat: Number(tracking.driverLat), lng: Number(tracking.driverLng) }
        : null,
    )) {
      return null;
    }

    return {
      lat: Number(tracking?.driverLat),
      lng: Number(tracking?.driverLng),
    };
  }, [tracking?.driverLat, tracking?.driverLng]);

  useEffect(() => {
    let mounted = true;

    const initializeMap = async () => {
      if (!containerRef.current || mapRef.current) {
        return;
      }

      try {
        await loadGoogleMapsAssets();
        if (!mounted || !containerRef.current || !window.google?.maps) {
          return;
        }

        mapRef.current = new window.google.maps.Map(containerRef.current, {
          zoom: DEFAULT_ZOOM,
          center: fallbackMarkerPosition,
          disableDefaultUI: true,
          gestureHandling: "greedy",
          clickableIcons: false,
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: false,
        });

        setMapReady(true);
      } catch {
        if (mounted) {
          setMapError("Não foi possível carregar o mapa agora.");
        }
      }
    };

    void initializeMap();

    return () => {
      mounted = false;
      driverAnimatorRef.current?.cancel();
      driverMarkerRef.current?.setMap(null);
      customerMarkerRef.current?.setMap(null);
      routeLineRef.current?.setMap(null);
      mapRef.current = null;
      driverMarkerRef.current = null;
      customerMarkerRef.current = null;
      routeLineRef.current = null;
    };
  }, [fallbackMarkerPosition]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !window.google?.maps) {
      return;
    }

    if (!customerMarkerRef.current) {
      customerMarkerRef.current = new window.google.maps.Marker({
        map,
        position: fallbackMarkerPosition,
        icon: {
          ...PLACEHOLDER_ICON,
          scaledSize: new window.google.maps.Size(PLACEHOLDER_ICON.scaledSize.width, PLACEHOLDER_ICON.scaledSize.height),
          anchor: new window.google.maps.Point(PLACEHOLDER_ICON.anchor.x, PLACEHOLDER_ICON.anchor.y),
        },
        title: resolvedDestination ? "Destino da entrega" : "Localização será exibida em breve",
        zIndex: 1,
      });
      return;
    }

    customerMarkerRef.current.setPosition(fallbackMarkerPosition);
  }, [fallbackMarkerPosition, resolvedDestination, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !window.google?.maps || !driverPosition || !isOutForDelivery) {
      if (driverMarkerRef.current && !isOutForDelivery) {
        driverMarkerRef.current.setMap(null);
        driverMarkerRef.current = null;
      }
      lastDriverPositionRef.current = null;
      driverAnimatorRef.current?.cancel();
      return;
    }

    if (!driverMarkerRef.current) {
      driverMarkerRef.current = new window.google.maps.Marker({
        map,
        position: driverPosition,
        icon: {
          ...MOTORCYCLE_ICON,
          scaledSize: new window.google.maps.Size(MOTORCYCLE_ICON.scaledSize.width, MOTORCYCLE_ICON.scaledSize.height),
          anchor: new window.google.maps.Point(MOTORCYCLE_ICON.anchor.x, MOTORCYCLE_ICON.anchor.y),
        },
        title: "Entregador",
        zIndex: 3,
      });
      driverAnimatorRef.current = new TrackingAnimator({
        setPosition: ([lng, lat]) => {
          driverMarkerRef.current?.setPosition({ lat, lng });
        },
      });
      lastDriverPositionRef.current = driverPosition;
      map.panTo(driverPosition);
      return;
    }

    const previousPosition = lastDriverPositionRef.current;
    if (previousPosition) {
      driverAnimatorRef.current?.animate(
        [previousPosition.lng, previousPosition.lat],
        [driverPosition.lng, driverPosition.lat],
      );
    } else {
      driverMarkerRef.current.setPosition(driverPosition);
    }

    lastDriverPositionRef.current = driverPosition;
    map.panTo(driverPosition);
  }, [driverPosition, isOutForDelivery, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !window.google?.maps) {
      return;
    }

    if (!isOutForDelivery || !driverPosition || !hasValidCoordinates(resolvedDestination)) {
      routeLineRef.current?.setMap(null);
      routeLineRef.current = null;
      return;
    }

    if (!routeLineRef.current) {
      routeLineRef.current = new window.google.maps.Polyline({
        map,
        geodesic: true,
        strokeColor: "#22c55e",
        strokeOpacity: 0.9,
        strokeWeight: 5,
      });
    }

    routeLineRef.current.setPath([driverPosition, resolvedDestination]);
  }, [driverPosition, isOutForDelivery, resolvedDestination, mapReady]);

  if (mapError) {
    return (
      <div className="flex h-[300px] w-full items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 px-4 text-center text-sm text-slate-500 shadow-sm">
        {mapError}
      </div>
    );
  }

  return (
    <div className="relative w-full overflow-hidden rounded-2xl border border-slate-200 bg-slate-100 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
      <div ref={containerRef} className="h-[360px] w-full transition-all duration-500" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-white/70 to-transparent" />
      {isDriverPositionLoading ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-slate-950/10 backdrop-blur-[1px]">
          <div className="flex items-center gap-3 rounded-full bg-white/92 px-4 py-2 text-sm font-medium text-slate-700 shadow-lg">
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-700" />
            Atualizando posição do entregador
          </div>
        </div>
      ) : null}
      <div className="pointer-events-none absolute bottom-3 left-3 rounded-full bg-white/90 px-3 py-1 text-[11px] font-medium text-slate-600 shadow-sm backdrop-blur">
        {isOutForDelivery ? "Rastreamento em tempo real" : "Mapa da entrega"}
      </div>
    </div>
  );
}
