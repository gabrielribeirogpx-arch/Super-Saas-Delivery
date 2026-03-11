"use client";

import { useEffect, useRef, useState } from "react";

type DeliveryMapProps = {
  orderId: number;
  driverLat?: number | null;
  driverLng?: number | null;
  driverHeading?: number | null;
  driverSpeed?: number | null;
  customerLat?: number | null;
  customerLng?: number | null;
  customerAddress?: string | null;
  navigationMode?: boolean;
  onMetricsChange?: (metrics: { eta: string | null; distance: string | null }) => void;
  onRouteChange?: (routeCoordinates: [number, number][]) => void;
  initialRouteCoordinates?: [number, number][] | null;
};

const ROUTE_RECALC_INTERVAL_MS = 10_000;
const ROUTE_DEVIATION_THRESHOLD_METERS = 50;
const CAMERA_UPDATE_INTERVAL_MS = 1000;
const MOVEMENT_SPEED_THRESHOLD_MPS = 0.5;
const CAMERA_DISTANCE_THRESHOLD_METERS = 5;
const GPS_SMOOTHING_ALPHA = 0.2;
const NAVIGATION_ZOOM = 17;
const NAVIGATION_TILT = 45;
const GOOGLE_MAPS_SCRIPT_ID = "google-maps-js";

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

  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  if (!apiKey) {
    return Promise.reject(new Error("Google Maps API key is missing"));
  }

  window.__googleMapsScriptLoadingPromise = new Promise<void>((resolve, reject) => {
    const existingScript = document.getElementById(GOOGLE_MAPS_SCRIPT_ID) as HTMLScriptElement | null;
    if (existingScript) {
      existingScript.addEventListener("load", () => resolve(), { once: true });
      existingScript.addEventListener("error", () => reject(new Error("Failed to load Google Maps")), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.id = GOOGLE_MAPS_SCRIPT_ID;
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}`;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Google Maps"));
    document.body.appendChild(script);
  });

  return window.__googleMapsScriptLoadingPromise;
}

function distanceInMeters(pointA: [number, number], pointB: [number, number]) {
  const toRad = (value: number) => (value * Math.PI) / 180;
  const earthRadius = 6371000;
  const dLat = toRad(pointB[1] - pointA[1]);
  const dLng = toRad(pointB[0] - pointA[0]);
  const lat1 = toRad(pointA[1]);
  const lat2 = toRad(pointB[1]);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * earthRadius * Math.asin(Math.sqrt(a));
}

function smoothPosition(newPos: { lat: number; lng: number }, lastPos: { lat: number; lng: number } | null) {
  if (!lastPos) {
    return newPos;
  }

  return {
    lat: lastPos.lat + GPS_SMOOTHING_ALPHA * (newPos.lat - lastPos.lat),
    lng: lastPos.lng + GPS_SMOOTHING_ALPHA * (newPos.lng - lastPos.lng),
  };
}

function normalizeHeading(heading?: number | null) {
  if (!Number.isFinite(heading)) {
    return 0;
  }

  return ((heading as number) % 360 + 360) % 360;
}

function distanceFromRoute(driver: [number, number], routeCoordinates: [number, number][]) {
  if (routeCoordinates.length === 0) {
    return Number.POSITIVE_INFINITY;
  }

  let minDistance = Number.POSITIVE_INFINITY;
  for (const coordinate of routeCoordinates) {
    const candidateDistance = distanceInMeters(driver, coordinate);
    if (candidateDistance < minDistance) {
      minDistance = candidateDistance;
    }
  }

  return minDistance;
}

export default function DeliveryMap({
  orderId,
  driverLat,
  driverLng,
  driverHeading,
  driverSpeed,
  customerLat,
  customerLng,
  customerAddress,
  navigationMode = false,
  onMetricsChange,
  onRouteChange,
  initialRouteCoordinates = null,
}: DeliveryMapProps) {
  const mapRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const destinationMarkerRef = useRef<any>(null);
  const driverMarkerRef = useRef<any>(null);
  const directionsServiceRef = useRef<any>(null);
  const directionsRendererRef = useRef<any>(null);
  const geocoderRef = useRef<any>(null);
  const latestOrderIdRef = useRef(orderId);
  const lastCameraUpdateAtRef = useRef(0);
  const lastCoordsRef = useRef<{ lat: number; lng: number } | null>(null);
  const markerHeadingRef = useRef(0);
  const [isMapReady, setIsMapReady] = useState(false);
  const lastRouteRefreshAtRef = useRef(0);
  const lastRouteCoordsRef = useRef<[number, number][]>([]);
  const routeFetchInFlightRef = useRef(false);
  const onMetricsChangeRef = useRef(onMetricsChange);
  const onRouteChangeRef = useRef(onRouteChange);
  const lastMetricsRef = useRef<{ eta: string | null; distance: string | null }>({ eta: null, distance: null });
  const [destinationCoords, setDestinationCoords] = useState<{ lat: number; lng: number } | null>(null);

  useEffect(() => {
    onMetricsChangeRef.current = onMetricsChange;
  }, [onMetricsChange]);

  useEffect(() => {
    onRouteChangeRef.current = onRouteChange;
  }, [onRouteChange]);

  useEffect(() => {
    latestOrderIdRef.current = orderId;
  }, [orderId]);

  useEffect(() => {
    let cancelled = false;

    const resolveDestination = async () => {
      if (Number.isFinite(customerLat) && Number.isFinite(customerLng)) {
        setDestinationCoords({ lat: customerLat as number, lng: customerLng as number });
        return;
      }

      if (!customerAddress?.trim() || !geocoderRef.current) {
        setDestinationCoords(null);
        return;
      }

      geocoderRef.current.geocode({ address: customerAddress }, (results: any, status: string) => {
        if (cancelled || latestOrderIdRef.current !== orderId || status !== "OK") {
          return;
        }

        const location = results?.[0]?.geometry?.location;
        if (!location) {
          return;
        }

        setDestinationCoords({ lat: location.lat(), lng: location.lng() });
      });
    };

    resolveDestination();

    return () => {
      cancelled = true;
    };
  }, [orderId, customerAddress, customerLat, customerLng, isMapReady]);

  useEffect(() => {
    let mounted = true;

    const getCurrentPosition = () =>
      new Promise<{ lat: number; lng: number }>((resolve, reject) => {
        if (!navigator.geolocation) {
          reject(new Error("Geolocation not supported"));
          return;
        }

        navigator.geolocation.getCurrentPosition(
          (position) => {
            resolve({ lat: position.coords.latitude, lng: position.coords.longitude });
          },
          (error) => reject(error),
          {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0,
          },
        );
      });

    (async () => {
      if (!containerRef.current || mapRef.current) {
        return;
      }

      await loadGoogleMapsAssets();
      if (!window.google?.maps || !mounted) {
        return;
      }

      const liveDriver = Number.isFinite(driverLat) && Number.isFinite(driverLng) ? { lat: driverLat as number, lng: driverLng as number } : null;
      const gpsDriver = await getCurrentPosition().catch(() => null);
      const initialDriver = gpsDriver ?? liveDriver;
      const fallbackDestination = Number.isFinite(customerLat) && Number.isFinite(customerLng)
        ? { lat: customerLat as number, lng: customerLng as number }
        : null;
      const initialCenter = initialDriver ?? fallbackDestination;

      if (!initialCenter) {
        return;
      }

      mapRef.current = new window.google.maps.Map(containerRef.current, {
        zoom: NAVIGATION_ZOOM,
        center: initialCenter,
        tilt: NAVIGATION_TILT,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
      });

      directionsServiceRef.current = new window.google.maps.DirectionsService();
      directionsRendererRef.current = new window.google.maps.DirectionsRenderer({
        map: mapRef.current,
        suppressMarkers: true,
        preserveViewport: true,
        polylineOptions: {
          strokeColor: "#007AFF",
          strokeOpacity: 0.95,
          strokeWeight: 6,
        },
      });
      geocoderRef.current = new window.google.maps.Geocoder();

      setIsMapReady(true);
    })();

    return () => {
      mounted = false;
      setIsMapReady(false);
      destinationMarkerRef.current?.setMap(null);
      driverMarkerRef.current?.setMap(null);
      directionsRendererRef.current?.setMap(null);
      destinationMarkerRef.current = null;
      driverMarkerRef.current = null;
      directionsRendererRef.current = null;
      directionsServiceRef.current = null;
      geocoderRef.current = null;
      mapRef.current = null;
    };
  }, [customerLat, customerLng, driverLat, driverLng]);

  useEffect(() => {
    lastCoordsRef.current = null;
    lastRouteRefreshAtRef.current = 0;
    lastRouteCoordsRef.current = initialRouteCoordinates ?? [];
    routeFetchInFlightRef.current = false;

    if (!isMapReady || !initialRouteCoordinates?.length || !directionsRendererRef.current || !window.google?.maps) {
      return;
    }

    const path = initialRouteCoordinates.map(([lng, lat]) => ({ lat, lng }));
    const directions = {
      routes: [
        {
          overview_path: path,
          legs: [],
        },
      ],
      request: {
        travelMode: window.google.maps.TravelMode.DRIVING,
      },
    };

    directionsRendererRef.current.setDirections(directions);
  }, [orderId, initialRouteCoordinates, isMapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !Number.isFinite(driverLat) || !Number.isFinite(driverLng) || !window.google?.maps) {
      return;
    }

    const rawPosition = { lat: driverLat as number, lng: driverLng as number };
    const smoothedPosition = smoothPosition(rawPosition, lastCoordsRef.current);
    const heading = normalizeHeading(driverHeading);
    const speed = Number.isFinite(driverSpeed) ? (driverSpeed as number) : 0;
    const now = Date.now();
    const hasLastPosition = Boolean(lastCoordsRef.current);
    const movementDistance = hasLastPosition
      ? distanceInMeters([lastCoordsRef.current!.lng, lastCoordsRef.current!.lat], [smoothedPosition.lng, smoothedPosition.lat])
      : Number.POSITIVE_INFINITY;
    const elapsedSinceCameraUpdate = now - lastCameraUpdateAtRef.current;
    const shouldUpdateCamera =
      navigationMode &&
      (movementDistance > CAMERA_DISTANCE_THRESHOLD_METERS || elapsedSinceCameraUpdate >= CAMERA_UPDATE_INTERVAL_MS);

    const position = new window.google.maps.LatLng(smoothedPosition.lat, smoothedPosition.lng);

    if (!driverMarkerRef.current) {
      driverMarkerRef.current = new window.google.maps.Marker({
        position,
        map,
        zIndex: 100,
        icon: {
          path: window.google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
          scale: 6,
          fillColor: "#2563eb",
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 2,
          rotation: heading,
        },
      });
      map.panTo(position);
    } else {
      driverMarkerRef.current.setPosition(position);
      const currentIcon = driverMarkerRef.current.getIcon();
      if (typeof currentIcon === "object") {
        driverMarkerRef.current.setIcon({
          ...currentIcon,
          rotation: heading,
        });
      }
    }

    if (shouldUpdateCamera) {
      const isMoving = speed > MOVEMENT_SPEED_THRESHOLD_MPS;
      map.panTo(position);
      map.setZoom(NAVIGATION_ZOOM);
      map.setTilt(NAVIGATION_TILT);
      if (isMoving) {
        map.setHeading(heading);
      }
      lastCameraUpdateAtRef.current = now;
    }

    markerHeadingRef.current = heading;
    lastCoordsRef.current = smoothedPosition;
  }, [driverLat, driverLng, driverHeading, driverSpeed, navigationMode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !destinationCoords || !window.google?.maps) {
      return;
    }

    if (!destinationMarkerRef.current) {
      destinationMarkerRef.current = new window.google.maps.Marker({
        position: destinationCoords,
        map,
        zIndex: 90,
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: 7,
          fillColor: "#e11d48",
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 2,
        },
      });
      return;
    }

    destinationMarkerRef.current.setPosition(destinationCoords);
  }, [destinationCoords]);

  useEffect(() => {
    if (!isMapReady || !Number.isFinite(driverLat) || !Number.isFinite(driverLng) || !destinationCoords) {
      return;
    }

    const directionsService = directionsServiceRef.current;
    const directionsRenderer = directionsRendererRef.current;
    if (!directionsService || !directionsRenderer || !window.google?.maps) {
      return;
    }

    const now = Date.now();
    const driverPoint: [number, number] = [driverLng as number, driverLat as number];
    const elapsedSinceRefresh = now - lastRouteRefreshAtRef.current;
    const distanceToExistingRoute = distanceFromRoute(driverPoint, lastRouteCoordsRef.current);
    const shouldRecalculateRoute =
      lastRouteCoordsRef.current.length === 0 ||
      elapsedSinceRefresh >= ROUTE_RECALC_INTERVAL_MS ||
      distanceToExistingRoute > ROUTE_DEVIATION_THRESHOLD_METERS;

    if (!shouldRecalculateRoute || routeFetchInFlightRef.current) {
      return;
    }

    routeFetchInFlightRef.current = true;

    directionsService.route(
      {
        origin: { lat: driverLat as number, lng: driverLng as number },
        destination: destinationCoords,
        travelMode: window.google.maps.TravelMode.DRIVING,
      },
      (result: any, status: string) => {
        routeFetchInFlightRef.current = false;

        if (status !== "OK" || !result || latestOrderIdRef.current !== orderId) {
          return;
        }

        directionsRenderer.setDirections(result);

        const leg = result.routes?.[0]?.legs?.[0];
        const nextMetrics = {
          eta: leg?.duration?.text ?? null,
          distance: leg?.distance?.text ?? null,
        };

        if (nextMetrics.eta !== lastMetricsRef.current.eta || nextMetrics.distance !== lastMetricsRef.current.distance) {
          lastMetricsRef.current = nextMetrics;
          onMetricsChangeRef.current?.(nextMetrics);
        }

        const overviewPath = result.routes?.[0]?.overview_path ?? [];
        const routeCoordinates = overviewPath.map((point: any) => [point.lng(), point.lat()] as [number, number]);
        if (routeCoordinates.length > 0) {
          lastRouteCoordsRef.current = routeCoordinates;
          onRouteChangeRef.current?.(routeCoordinates);
          lastRouteRefreshAtRef.current = Date.now();
        }

        if (!navigationMode && result.routes?.[0]?.bounds) {
          mapRef.current?.fitBounds(result.routes[0].bounds, 90);
        }
      },
    );
  }, [orderId, driverLat, driverLng, destinationCoords, navigationMode, isMapReady]);

  const handleRecenter = () => {
    if (!mapRef.current || !Number.isFinite(driverLat) || !Number.isFinite(driverLng) || !window.google?.maps) {
      return;
    }

    mapRef.current.panTo({ lat: driverLat as number, lng: driverLng as number });
    mapRef.current.setZoom(NAVIGATION_ZOOM);
    mapRef.current.setTilt(NAVIGATION_TILT);
    mapRef.current.setHeading(markerHeadingRef.current);
  };

  const handleOverview = () => {
    if (!mapRef.current || !Number.isFinite(driverLat) || !Number.isFinite(driverLng) || !destinationCoords || !window.google?.maps) {
      return;
    }

    const bounds = new window.google.maps.LatLngBounds();
    bounds.extend({ lat: driverLat as number, lng: driverLng as number });
    bounds.extend(destinationCoords);
    mapRef.current.fitBounds(bounds, 90);
  };

  return (
    <div className="fixed inset-0 z-0">
      <div ref={containerRef} className="h-full w-full" />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/25 via-transparent to-black/25" />
      <div className="absolute right-3 top-1/2 z-20 flex -translate-y-1/2 flex-col gap-2">
        <button
          type="button"
          onClick={handleRecenter}
          className="h-11 rounded-full bg-white/90 px-4 text-xs font-semibold text-slate-900 shadow-md backdrop-blur"
        >
          RECENTER
        </button>
        <button
          type="button"
          onClick={handleOverview}
          className="h-11 rounded-full bg-white/90 px-4 text-xs font-semibold text-slate-900 shadow-md backdrop-blur"
        >
          OVERVIEW
        </button>
      </div>
    </div>
  );
}
