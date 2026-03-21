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
};

const GOOGLE_MAPS_SCRIPT_ID = "google-maps-js";
const GOOGLE_MAPS_API_KEY = "AIzaSyCDi9WNbfW843u-GyJy4RNYWQ_2VDTrQiY";
const FALLBACK_CENTER = { lat: -23.5505, lng: -46.6333 };
const DEFAULT_ZOOM = 16;

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

export default function TrackingMap({ tracking, destination }: TrackingMapProps) {
  const destinationLat = tracking?.destinationLat ?? destination?.lat ?? null;
  const destinationLng = tracking?.destinationLng ?? destination?.lng ?? null;
  const driverLat = tracking?.driverLat ?? null;
  const driverLng = tracking?.driverLng ?? null;
  const resolvedDestination = hasValidCoordinates(
    destinationLat != null && destinationLng != null
      ? { lat: Number(destinationLat), lng: Number(destinationLng) }
      : null,
  )
    ? { lat: Number(destinationLat), lng: Number(destinationLng) }
    : null;

  console.log("DESTINATION:", destinationLat, destinationLng);
  console.log("DRIVER:", driverLat, driverLng);
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
  const isDriverPositionLoading = !hasDriverLocation;

  const driverPosition = useMemo<LatLngLiteral | null>(() => {
    if (driverLat === null || driverLng === null || !Number.isFinite(driverLat) || !Number.isFinite(driverLng)) {
      return null;
    }

    return {
      lat: Number(driverLat),
      lng: Number(driverLng),
    };
  }, [driverLat, driverLng]);

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
          center: FALLBACK_CENTER,
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
  }, []);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !window.google?.maps) {
      return;
    }

    const preferredCenter = driverPosition ?? resolvedDestination ?? null;
    if (!preferredCenter) {
      return;
    }

    if (!lastDriverPositionRef.current && driverPosition) {
      map.panTo(driverPosition);
      return;
    }

    if (!driverPosition && hasValidCoordinates(resolvedDestination)) {
      map.panTo(resolvedDestination);
    }
  }, [resolvedDestination, driverPosition, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !window.google?.maps || !hasValidCoordinates(resolvedDestination)) {
      return;
    }

    if (!customerMarkerRef.current) {
      customerMarkerRef.current = new window.google.maps.Marker({
        map,
        position: resolvedDestination,
        label: {
          text: "🏠",
          fontSize: "24px",
        },
        zIndex: 1,
      });
      return;
    }

    customerMarkerRef.current.setPosition(resolvedDestination);
  }, [resolvedDestination, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !window.google?.maps || !driverPosition) {
      return;
    }

    if (!driverMarkerRef.current) {
      driverMarkerRef.current = new window.google.maps.Marker({
        map,
        position: driverPosition,
        label: {
          text: "🏍️",
          fontSize: "24px",
        },
        zIndex: 2,
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
    const mapCenter = map.getCenter();
    const currentCenterLat = mapCenter?.lat() ?? driverPosition.lat;
    const currentCenterLng = mapCenter?.lng() ?? driverPosition.lng;

    map.panTo({
      lat: currentCenterLat + (driverPosition.lat - currentCenterLat) * 0.35,
      lng: currentCenterLng + (driverPosition.lng - currentCenterLng) * 0.35,
    });
  }, [driverPosition, mapReady]);

  useEffect(() => {
    const map = mapRef.current;

    if (!map || !window.google?.maps || !driverPosition || !hasValidCoordinates(resolvedDestination)) {
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
  }, [resolvedDestination, driverPosition, mapReady]);

  if (mapError) {
    return (
      <div className="flex h-[300px] w-full items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 px-4 text-center text-sm text-slate-500 shadow-sm">
        {mapError}
      </div>
    );
  }

  if (!resolvedDestination) {
    return (
      <div className="flex h-[300px] w-full items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 px-4 text-center text-sm text-slate-500 shadow-sm">
        Endereço do cliente não disponível
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
        Rastreamento em tempo real
      </div>
    </div>
  );
}
