"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type TrackingState = {
  driverLat?: number | null;
  driverLng?: number | null;
  distanceMeters?: number | null;
  durationSeconds?: number | null;
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
const DRIVER_MARKER_SCALE = 6;
const CUSTOMER_MARKER_SCALE = 8;

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
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const driverMarkerRef = useRef<any>(null);
  const customerMarkerRef = useRef<any>(null);
  const directionsServiceRef = useRef<any>(null);
  const directionsRendererRef = useRef<any>(null);
  const animationFrameRef = useRef<number | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);

  const driverPosition = useMemo<LatLngLiteral | null>(() => {
    if (!tracking || !Number.isFinite(tracking.driverLat) || !Number.isFinite(tracking.driverLng)) {
      return null;
    }

    return {
      lat: Number(tracking.driverLat),
      lng: Number(tracking.driverLng),
    };
  }, [tracking]);

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
          zoom: 15,
          center: driverPosition ?? destination ?? FALLBACK_CENTER,
          disableDefaultUI: true,
          gestureHandling: "greedy",
          clickableIcons: false,
        });

        directionsServiceRef.current = new window.google.maps.DirectionsService();
        directionsRendererRef.current = new window.google.maps.DirectionsRenderer({
          suppressMarkers: true,
          preserveViewport: true,
          polylineOptions: {
            strokeColor: "#22c55e",
            strokeWeight: 5,
          },
        });
        directionsRendererRef.current.setMap(mapRef.current);
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
      if (animationFrameRef.current != null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      driverMarkerRef.current?.setMap(null);
      customerMarkerRef.current?.setMap(null);
      directionsRendererRef.current?.setMap(null);
      mapRef.current = null;
      driverMarkerRef.current = null;
      customerMarkerRef.current = null;
      directionsServiceRef.current = null;
      directionsRendererRef.current = null;
    };
  }, [destination, driverPosition]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !window.google?.maps || !hasValidCoordinates(destination)) {
      return;
    }

    if (!customerMarkerRef.current) {
      customerMarkerRef.current = new window.google.maps.Marker({
        map,
        position: destination,
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: CUSTOMER_MARKER_SCALE,
          fillColor: "#22c55e",
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 2,
        },
        zIndex: 1,
      });
      return;
    }

    customerMarkerRef.current.setPosition(destination);
  }, [destination, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !window.google?.maps || !driverPosition) {
      return;
    }

    if (!driverMarkerRef.current) {
      driverMarkerRef.current = new window.google.maps.Marker({
        map,
        position: driverPosition,
        icon: {
          path: window.google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
          scale: DRIVER_MARKER_SCALE,
          fillColor: "#2563eb",
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 2,
          rotation: 0,
        },
        zIndex: 2,
      });
      map.panTo(driverPosition);
      return;
    }

    driverMarkerRef.current.setPosition(driverPosition);

    if (animationFrameRef.current != null) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    animationFrameRef.current = requestAnimationFrame(() => {
      map.panTo(driverPosition);
    });
  }, [driverPosition, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    const directionsService = directionsServiceRef.current;
    const directionsRenderer = directionsRendererRef.current;

    if (!map || !directionsService || !directionsRenderer || !window.google?.maps || !driverPosition || !hasValidCoordinates(destination)) {
      return;
    }

    directionsService.route(
      {
        origin: driverPosition,
        destination,
        travelMode: window.google.maps.TravelMode.DRIVING,
      },
      (result: any, status: string) => {
        if (status === "OK" && result) {
          directionsRenderer.setDirections(result);

          const bounds = new window.google.maps.LatLngBounds();
          bounds.extend(driverPosition);
          bounds.extend(destination);
          map.fitBounds(bounds, 48);
        }
      },
    );
  }, [destination, driverPosition, mapReady]);

  if (!driverPosition) {
    return (
      <div className="flex h-[300px] w-full items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm text-slate-500 shadow-sm animate-in fade-in duration-300">
        Localizando entregador...
      </div>
    );
  }

  if (mapError) {
    return (
      <div className="flex h-[300px] w-full items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 px-4 text-center text-sm text-slate-500 shadow-sm">
        {mapError}
      </div>
    );
  }

  return (
    <div className="relative w-full overflow-hidden rounded-2xl border border-slate-200 bg-slate-100 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
      <div ref={containerRef} className="h-[300px] w-full transition-all duration-500" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-white/70 to-transparent" />
      <div className="pointer-events-none absolute bottom-3 left-3 rounded-full bg-white/90 px-3 py-1 text-[11px] font-medium text-slate-600 shadow-sm backdrop-blur">
        Atualização em tempo real
      </div>
    </div>
  );
}
