"use client";

import { useEffect, useRef, useState } from "react";
import { t } from "@/i18n/translate";
import { GOOGLE_MAPS_API_KEY, GOOGLE_MAPS_SCRIPT_ID, getGoogleMapsMissingKeyMessage } from "@/lib/maps/googleMapsConfig";

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
  onMapReadyChange?: (isReady: boolean) => void;
  onRecenter?: () => void;
  onOverview?: () => void;
  onFollowModeChange?: (isFollowing: boolean) => void;
  onNavigationUpdate?: (payload: { eta: string | null; distance: string | null; instruction: string | null; instructionDistance: string | null }) => void;
};

const ROUTE_RECALC_INTERVAL_MS = 10_000;
const ROUTE_DEVIATION_THRESHOLD_METERS = 40;
const CAMERA_UPDATE_INTERVAL_MS = 1000;
const MOVEMENT_SPEED_THRESHOLD_MPS = 0.5;
const CAMERA_DISTANCE_THRESHOLD_METERS = 5;
const GPS_SMOOTHING_ALPHA = 0.25;
const NAVIGATION_ZOOM = 18;
const NAVIGATION_TILT = 60;
const DEFAULT_LOCATION = { lat: -21.99, lng: -48.39 };

declare global {
  interface Window {
    google?: any;
    __googleMapsScriptLoadingPromise?: Promise<void>;
    driverMapInstance?: any;
  }
}

function waitForGoogle(callback: () => void) {
  if (typeof window !== "undefined" && window.google?.maps) {
    callback();
    return;
  }

  setTimeout(() => waitForGoogle(callback), 200);
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

  if (!GOOGLE_MAPS_API_KEY) {
    const error = new Error(getGoogleMapsMissingKeyMessage("DeliveryMap"));
    window.__googleMapsScriptLoadingPromise = Promise.reject(error);
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

function hasValidCoordinates(lat?: number | null, lng?: number | null) {
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return false;
  }

  return (lat as number) >= -90 && (lat as number) <= 90 && (lng as number) >= -180 && (lng as number) <= 180;
}

function formatDistance(distanceMeters: number) {
  if (!Number.isFinite(distanceMeters) || distanceMeters < 0) {
    return null;
  }

  if (distanceMeters >= 1000) {
    return `${(distanceMeters / 1000).toFixed(1)} km`;
  }

  return `${Math.round(distanceMeters)} m`;
}

function formatEta(durationSeconds: number) {
  if (!Number.isFinite(durationSeconds) || durationSeconds < 0) {
    return null;
  }

  const minutes = Math.max(1, Math.round(durationSeconds / 60));
  return `${minutes} min`;
}

function stripHtml(value: string) {
  return value.replace(/<[^>]*>/g, "").trim();
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
  onMapReadyChange,
  onRecenter,
  onOverview,
  onFollowModeChange,
  onNavigationUpdate,
}: DeliveryMapProps) {
  const mapRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const destinationMarkerRef = useRef<any>(null);
  const driverMarkerRef = useRef<any>(null);
  const directionsServiceRef = useRef<any>(null);
  const directionsRendererRef = useRef<any>(null);
  const latestOrderIdRef = useRef(orderId);
  const lastCameraUpdateAtRef = useRef(0);
  const lastCoordsRef = useRef<{ lat: number; lng: number } | null>(null);
  const markerHeadingRef = useRef(0);
  const followingModeRef = useRef(navigationMode);
  const routePolylineRef = useRef<any>(null);
  const routePathRef = useRef<{ lat: number; lng: number }[]>([]);
  const routeLegRef = useRef<{ distanceMeters: number; durationSeconds: number; steps: { instruction: string; endDistanceMeters: number }[] } | null>(null);
  const [isMapReady, setIsMapReady] = useState(false);
  const lastRouteRefreshAtRef = useRef(0);
  const lastRouteCoordsRef = useRef<[number, number][]>([]);
  const routeFetchInFlightRef = useRef(false);
  const onMetricsChangeRef = useRef(onMetricsChange);
  const onRouteChangeRef = useRef(onRouteChange);
  const onMapReadyChangeRef = useRef(onMapReadyChange);
  const lastMetricsRef = useRef<{ eta: string | null; distance: string | null }>({ eta: null, distance: null });
  const [destinationCoords, setDestinationCoords] = useState<{ lat: number; lng: number } | null>(null);

  const projectOnRoute = (point: { lat: number; lng: number }) => {
    const path = routePathRef.current;
    if (path.length < 2) {
      return null;
    }

    let best: { lat: number; lng: number; segmentIndex: number; t: number; distanceMeters: number } | null = null;
    const cosLat = Math.cos((point.lat * Math.PI) / 180);

    for (let index = 0; index < path.length - 1; index += 1) {
      const start = path[index];
      const end = path[index + 1];
      const ax = (start.lng - point.lng) * 111320 * cosLat;
      const ay = (start.lat - point.lat) * 110540;
      const bx = (end.lng - point.lng) * 111320 * cosLat;
      const by = (end.lat - point.lat) * 110540;
      const abx = bx - ax;
      const aby = by - ay;
      const denom = abx * abx + aby * aby;
      const t = denom === 0 ? 0 : Math.max(0, Math.min(1, -(ax * abx + ay * aby) / denom));
      const px = ax + abx * t;
      const py = ay + aby * t;
      const distanceMeters = Math.hypot(px, py);

      if (!best || distanceMeters < best.distanceMeters) {
        best = {
          lat: start.lat + (end.lat - start.lat) * t,
          lng: start.lng + (end.lng - start.lng) * t,
          segmentIndex: index,
          t,
          distanceMeters,
        };
      }
    }

    return best;
  };

  const remainingDistanceMeters = (projection: { segmentIndex: number; t: number }) => {
    const path = routePathRef.current;
    if (path.length < 2) {
      return 0;
    }

    let remaining = 0;
    const start = path[projection.segmentIndex];
    const end = path[projection.segmentIndex + 1];
    const snappedPoint: [number, number] = [
      start.lng + (end.lng - start.lng) * projection.t,
      start.lat + (end.lat - start.lat) * projection.t,
    ];
    remaining += distanceInMeters(snappedPoint, [end.lng, end.lat]);

    for (let index = projection.segmentIndex + 1; index < path.length - 1; index += 1) {
      remaining += distanceInMeters([path[index].lng, path[index].lat], [path[index + 1].lng, path[index + 1].lat]);
    }

    return remaining;
  };

  useEffect(() => {
    onMetricsChangeRef.current = onMetricsChange;
  }, [onMetricsChange]);

  useEffect(() => {
    onRouteChangeRef.current = onRouteChange;
  }, [onRouteChange]);

  useEffect(() => {
    onMapReadyChangeRef.current = onMapReadyChange;
  }, [onMapReadyChange]);

  useEffect(() => {
    latestOrderIdRef.current = orderId;
  }, [orderId]);

  useEffect(() => {
    followingModeRef.current = navigationMode;
  }, [navigationMode]);

  useEffect(() => {
    if (hasValidCoordinates(customerLat, customerLng)) {
      const nextDestination = { lat: customerLat as number, lng: customerLng as number };
      setDestinationCoords(nextDestination);
      console.log("[DriverMap] order destination coordinates", { orderId, ...nextDestination });
      return;
    }

    setDestinationCoords(null);
    console.warn("[DriverMap] missing/invalid destination coordinates", {
      orderId,
      customerLat,
      customerLng,
      customerAddress,
    });
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

    const initGoogleMap = async () => {
      if (!containerRef.current || mapRef.current || !window.google?.maps || !mounted) {
        return;
      }

      const liveDriver = Number.isFinite(driverLat) && Number.isFinite(driverLng) ? { lat: driverLat as number, lng: driverLng as number } : null;
      const fallbackDestination = Number.isFinite(customerLat) && Number.isFinite(customerLng)
        ? { lat: customerLat as number, lng: customerLng as number }
        : null;
      const initialCenter = liveDriver ?? fallbackDestination ?? DEFAULT_LOCATION;

      const containerHeight = containerRef.current.clientHeight;
      console.log("[DriverMap] container height", containerHeight);

      mapRef.current = new window.google.maps.Map(containerRef.current, {
        zoom: NAVIGATION_ZOOM,
        center: initialCenter,
        tilt: NAVIGATION_TILT,
        disableDefaultUI: false,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
      });
      console.log("[DriverMap] map initialized", initialCenter);
      void getCurrentPosition()
        .then((gpsDriver) => {
          if (!mounted || !mapRef.current || liveDriver) {
            return;
          }

          mapRef.current.setCenter(gpsDriver);
        })
        .catch(() => {
          // GPS unavailable should not block map rendering.
        });
      window.google.maps.event.trigger(mapRef.current, "resize");
      window.driverMapInstance = mapRef.current;

      directionsServiceRef.current = new window.google.maps.DirectionsService();
      directionsRendererRef.current = new window.google.maps.DirectionsRenderer({
        suppressMarkers: false,
        suppressPolylines: true,
        preserveViewport: true,
      });
      directionsRendererRef.current.setMap(mapRef.current);
      routePolylineRef.current = new window.google.maps.Polyline({
        map: mapRef.current,
        path: [],
        strokeColor: "#4285F4",
        strokeOpacity: 0.95,
        strokeWeight: 7,
        zIndex: 80,
      });
      mapRef.current.addListener("dragstart", () => {
        if (!followingModeRef.current) {
          return;
        }

        followingModeRef.current = false;
        onFollowModeChange?.(false);
      });
      setIsMapReady(true);
      onMapReadyChangeRef.current?.(true);
    };

    const initializeWhenReady = () => {
      waitForGoogle(() => {
        const ensureContainerAndInit = () => {
          const mapDiv = containerRef.current ?? (document.getElementById("driver-map") as HTMLDivElement | null);
          if (!mounted || mapRef.current || !mapDiv) {
            return;
          }

          const style = window.getComputedStyle(mapDiv);
          const isVisible = style.display !== "none" && style.visibility !== "hidden";
          const hasValidHeight = mapDiv.clientHeight > 0;
          const hasValidWidth = mapDiv.clientWidth > 0;

          if (!isVisible || !hasValidHeight || !hasValidWidth) {
            window.setTimeout(ensureContainerAndInit, 200);
            return;
          }

          void initGoogleMap();
        };

        ensureContainerAndInit();
      });
    };

    const onDomReady = () => {
      void loadGoogleMapsAssets()
        .then(() => {
          initializeWhenReady();
        })
        .catch(() => {
          setIsMapReady(false);
          onMapReadyChangeRef.current?.(false);
        });
    };

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", onDomReady, { once: true });
    } else {
      onDomReady();
    }

    return () => {
      document.removeEventListener("DOMContentLoaded", onDomReady);
      mounted = false;
      setIsMapReady(false);
      onMapReadyChangeRef.current?.(false);
      destinationMarkerRef.current?.setMap(null);
      driverMarkerRef.current?.setMap(null);
      directionsRendererRef.current?.setMap(null);
      routePolylineRef.current?.setMap(null);
      destinationMarkerRef.current = null;
      driverMarkerRef.current = null;
      directionsRendererRef.current = null;
      directionsServiceRef.current = null;
      routePolylineRef.current = null;
      mapRef.current = null;
      window.driverMapInstance = undefined;
    };
  }, []);

  useEffect(() => {
    lastCoordsRef.current = null;
    lastRouteRefreshAtRef.current = 0;
    lastRouteCoordsRef.current = initialRouteCoordinates ?? [];
    routeFetchInFlightRef.current = false;

    if (!navigationMode || !isMapReady || !initialRouteCoordinates?.length || !directionsRendererRef.current || !window.google?.maps) {
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
    routePathRef.current = path;
    routePolylineRef.current?.setPath(path);
  }, [orderId, initialRouteCoordinates, isMapReady, navigationMode]);

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

    const projected = projectOnRoute(smoothedPosition);
    const snappedPosition = projected ? { lat: projected.lat, lng: projected.lng } : smoothedPosition;
    const position = new window.google.maps.LatLng(snappedPosition.lat, snappedPosition.lng);

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

    if (projected) {
      const remainingPath = routePathRef.current.slice(projected.segmentIndex + 1);
      routePolylineRef.current?.setPath([
        { lat: projected.lat, lng: projected.lng },
        ...remainingPath,
      ]);

      const remainingDistance = remainingDistanceMeters(projected);
      const leg = routeLegRef.current;
      const etaSeconds = leg?.distanceMeters ? (remainingDistance / leg.distanceMeters) * leg.durationSeconds : Number.NaN;
      const traveled = Math.max(0, (leg?.distanceMeters ?? 0) - remainingDistance);
      const nextStep = leg?.steps.find((step) => step.endDistanceMeters > traveled);
      const nextUpdate = {
        eta: formatEta(etaSeconds),
        distance: formatDistance(remainingDistance),
        instruction: nextStep?.instruction ?? null,
        instructionDistance: nextStep ? formatDistance(nextStep.endDistanceMeters - traveled) : null,
      };
      onNavigationUpdate?.(nextUpdate);
      if (nextUpdate.eta !== lastMetricsRef.current.eta || nextUpdate.distance !== lastMetricsRef.current.distance) {
        lastMetricsRef.current = { eta: nextUpdate.eta, distance: nextUpdate.distance };
        onMetricsChangeRef.current?.({ eta: nextUpdate.eta, distance: nextUpdate.distance });
      }
    }

    if (shouldUpdateCamera && followingModeRef.current) {
      const isMoving = speed > MOVEMENT_SPEED_THRESHOLD_MPS;
      map.moveCamera({
        center: position,
        zoom: 18,
        tilt: NAVIGATION_TILT,
        heading: isMoving ? heading : markerHeadingRef.current,
      });
      lastCameraUpdateAtRef.current = now;
    } else if (!navigationMode) {
      map.panTo(position);
    }

    markerHeadingRef.current = heading;
    lastCoordsRef.current = snappedPosition;
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
    if (!navigationMode || !isMapReady || !Number.isFinite(driverLat) || !Number.isFinite(driverLng) || !destinationCoords) {
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
        console.log("[DriverMap] directions response", { status });
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
        const path = overviewPath.map((point: any) => ({ lat: point.lat(), lng: point.lng() }));
        routePathRef.current = path;
        routePolylineRef.current?.setPath(path);
        const routeCoordinates = overviewPath.map((point: any) => [point.lng(), point.lat()] as [number, number]);
        const steps = (leg?.steps ?? []).map((step: any, index: number, all: any[]) => {
          const endDistanceMeters = all.slice(0, index + 1).reduce((sum: number, item: any) => sum + (item?.distance?.value ?? 0), 0);
          return {
            instruction: stripHtml(step?.instructions ?? t("continue")),
            endDistanceMeters,
          };
        });
        routeLegRef.current = {
          distanceMeters: leg?.distance?.value ?? 0,
          durationSeconds: leg?.duration?.value ?? 0,
          steps,
        };
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
    onRecenter?.();
    followingModeRef.current = true;
    onFollowModeChange?.(true);

    if (!mapRef.current || !Number.isFinite(driverLat) || !Number.isFinite(driverLng) || !window.google?.maps) {
      return;
    }

    mapRef.current.panTo({ lat: driverLat as number, lng: driverLng as number });
    mapRef.current.setZoom(NAVIGATION_ZOOM);
    mapRef.current.setTilt(NAVIGATION_TILT);
    mapRef.current.setHeading(markerHeadingRef.current);
  };

  const handleOverview = () => {
    onOverview?.();
    followingModeRef.current = false;
    onFollowModeChange?.(false);

    directionsRendererRef.current?.setMap(mapRef.current);

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
      <div id="driver-map" ref={containerRef} className="h-full w-full" style={{ minHeight: "400px", height: "100vh" }} />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/25 via-transparent to-black/25" />
      <div className="absolute right-3 top-1/2 z-20 flex -translate-y-1/2 flex-col gap-2">
        <button
          type="button"
          onClick={handleRecenter}
          className="h-11 rounded-full bg-white/90 px-4 text-xs font-semibold text-slate-900 shadow-md backdrop-blur"
        >
          {t("recenter")}
        </button>
        <button
          type="button"
          onClick={handleOverview}
          className="h-11 rounded-full bg-white/90 px-4 text-xs font-semibold text-slate-900 shadow-md backdrop-blur"
        >
          {t("overview")}
        </button>
      </div>
    </div>
  );
}
