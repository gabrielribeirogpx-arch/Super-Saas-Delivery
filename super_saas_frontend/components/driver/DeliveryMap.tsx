"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import mapboxgl, { type GeoJSONSource, type Map as MapboxMap, type Marker } from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { t } from "@/i18n/translate";

type Coordinates = [number, number];
type Metrics = { eta: string | null; distance: string | null };
type Navigation = Metrics & { instruction: string | null; instructionDistance: string | null };
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
  onMetricsChange?: (metrics: Metrics) => void;
  onRouteChange?: (routeCoordinates: Coordinates[]) => void;
  initialRouteCoordinates?: Coordinates[] | null;
  onMapReadyChange?: (isReady: boolean) => void;
  onRecenter?: () => void;
  onOverview?: () => void;
  onFollowModeChange?: (isFollowing: boolean) => void;
  onNavigationUpdate?: (payload: Navigation) => void;
};

const TOKEN = process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN?.trim()
  || process.env.NEXT_PUBLIC_MAPBOX_TOKEN?.trim() || "";
const ROUTE_SOURCE = "driver-route";
const NAVIGATION_ZOOM = 17.5;
const NAVIGATION_PITCH = 60;

function valid(lat?: number | null, lng?: number | null) {
  return lat != null && lng != null && Number.isFinite(lat) && Number.isFinite(lng)
    && Math.abs(lat) <= 90 && Math.abs(lng) <= 180;
}

function routeData(coordinates: Coordinates[]): Parameters<GeoJSONSource["setData"]>[0] {
  return coordinates.length < 2
    ? { type: "FeatureCollection", features: [] }
    : {
      type: "Feature",
      properties: {},
      geometry: { type: "LineString", coordinates },
    } as Parameters<GeoJSONSource["setData"]>[0];
}

function formatDistance(meters: number) {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}

function formatEta(seconds: number) {
  return `${Math.max(1, Math.ceil(seconds / 60))} min`;
}

function marker(kind: "driver" | "destination") {
  const element = document.createElement("div");
  element.style.cssText = kind === "driver"
    ? "width:32px;height:32px;border:4px solid white;border-radius:50%;background:#1769e0;box-shadow:0 2px 12px #11182799;"
    : "width:26px;height:26px;border:5px solid white;border-radius:50%;background:#cf0714;box-shadow:0 2px 12px #11182799;";
  element.setAttribute("aria-label", kind === "driver" ? "Entregador" : "Cliente");
  return element;
}

export default function DeliveryMap({
  orderId,
  driverLat,
  driverLng,
  driverHeading,
  customerLat,
  customerLng,
  navigationMode = false,
  onMetricsChange,
  onRouteChange,
  initialRouteCoordinates,
  onMapReadyChange,
  onRecenter,
  onOverview,
  onFollowModeChange,
  onNavigationUpdate,
}: DeliveryMapProps) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapboxMap | null>(null);
  const driverMarker = useRef<Marker | null>(null);
  const destinationMarker = useRef<Marker | null>(null);
  const request = useRef<AbortController | null>(null);
  const lastRouteAt = useRef(0);
  const lastRouteOrigin = useRef<Coordinates | null>(null);
  const latestOrder = useRef(orderId);
  const following = useRef(navigationMode);
  const callbacks = useRef({ onMetricsChange, onRouteChange, onMapReadyChange, onFollowModeChange, onNavigationUpdate });
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    callbacks.current = { onMetricsChange, onRouteChange, onMapReadyChange, onFollowModeChange, onNavigationUpdate };
  }, [onMetricsChange, onRouteChange, onMapReadyChange, onFollowModeChange, onNavigationUpdate]);
  useEffect(() => { following.current = navigationMode; }, [navigationMode]);
  useEffect(() => {
    latestOrder.current = orderId;
    request.current?.abort();
    lastRouteAt.current = 0;
    lastRouteOrigin.current = null;
  }, [orderId]);

  useEffect(() => {
    if (!container.current || !TOKEN.startsWith("pk.")) {
      setError(true);
      callbacks.current.onMapReadyChange?.(false);
      return;
    }
    mapboxgl.accessToken = TOKEN;
    const instance = new mapboxgl.Map({
      container: container.current,
      style: "mapbox://styles/mapbox/streets-v12",
      center: valid(driverLat, driverLng) ? [driverLng!, driverLat!] : [-48.39, -21.99],
      zoom: NAVIGATION_ZOOM,
      pitch: NAVIGATION_PITCH,
    });
    map.current = instance;
    instance.on("load", () => {
      instance.addSource(ROUTE_SOURCE, { type: "geojson", data: routeData([]) });
      instance.addLayer({
        id: "driver-route-outline",
        source: ROUTE_SOURCE,
        type: "line",
        paint: { "line-color": "#fff", "line-width": 10 },
        layout: { "line-cap": "round", "line-join": "round" },
      });
      instance.addLayer({
        id: "driver-route-line",
        source: ROUTE_SOURCE,
        type: "line",
        paint: { "line-color": "#1769e0", "line-width": 7 },
        layout: { "line-cap": "round", "line-join": "round" },
      });
      setReady(true);
      callbacks.current.onMapReadyChange?.(true);
    });
    instance.on("dragstart", () => {
      if (following.current) {
        following.current = false;
        callbacks.current.onFollowModeChange?.(false);
      }
    });
    instance.on("error", () => setError(true));
    return () => {
      request.current?.abort();
      driverMarker.current?.remove();
      destinationMarker.current?.remove();
      map.current = null;
      instance.remove();
      callbacks.current.onMapReadyChange?.(false);
    };
  }, []);

  const drawRoute = useCallback((coordinates: Coordinates[]) => {
    (map.current?.getSource(ROUTE_SOURCE) as GeoJSONSource | undefined)?.setData(routeData(coordinates));
  }, []);

  useEffect(() => {
    if (!ready || !map.current) return;
    drawRoute(initialRouteCoordinates ?? []);
  }, [orderId, initialRouteCoordinates, ready, drawRoute]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !ready || !valid(customerLat, customerLng)) return;
    const point: Coordinates = [customerLng!, customerLat!];
    if (!destinationMarker.current) {
      destinationMarker.current = new mapboxgl.Marker({ element: marker("destination") })
        .setLngLat(point).addTo(instance);
    } else {
      destinationMarker.current.setLngLat(point);
    }
  }, [customerLat, customerLng, ready]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !ready || !valid(driverLat, driverLng)) return;
    const point: Coordinates = [driverLng!, driverLat!];
    if (!driverMarker.current) {
      driverMarker.current = new mapboxgl.Marker({ element: marker("driver") })
        .setLngLat(point).addTo(instance);
    } else {
      driverMarker.current.setLngLat(point);
    }
    if (following.current) {
      instance.easeTo({
        center: point,
        zoom: NAVIGATION_ZOOM,
        pitch: NAVIGATION_PITCH,
        bearing: Number.isFinite(driverHeading) ? driverHeading! : 0,
        duration: 500,
      });
    }
  }, [driverLat, driverLng, driverHeading, ready]);

  useEffect(() => {
    if (!ready || !navigationMode || !valid(driverLat, driverLng)
      || !valid(customerLat, customerLng)) return;
    const origin: Coordinates = [driverLng!, driverLat!];
    const previous = lastRouteOrigin.current;
    const moved = !previous || Math.hypot(origin[0] - previous[0], origin[1] - previous[1]) > 0.00035;
    if (!moved && Date.now() - lastRouteAt.current < 30_000) return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    lastRouteAt.current = Date.now();
    lastRouteOrigin.current = origin;
    const coordinates = `${origin[0]},${origin[1]};${customerLng},${customerLat}`;
    const url = new URL(`https://api.mapbox.com/directions/v5/mapbox/driving/${coordinates}`);
    url.searchParams.set("access_token", TOKEN);
    url.searchParams.set("geometries", "geojson");
    url.searchParams.set("overview", "full");
    url.searchParams.set("steps", "true");
    url.searchParams.set("language", "pt-BR");
    void fetch(url, { signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Route unavailable")))
      .then((data) => {
        if (controller.signal.aborted || latestOrder.current !== orderId || data.code !== "Ok") return;
        const route = data.routes?.[0];
        const path = route?.geometry?.coordinates as Coordinates[] | undefined;
        if (!Array.isArray(path) || path.length < 2) return;
        drawRoute(path);
        callbacks.current.onRouteChange?.(path);
        const metrics = { eta: formatEta(route.duration), distance: formatDistance(route.distance) };
        callbacks.current.onMetricsChange?.(metrics);
        const firstStep = route.legs?.[0]?.steps?.[0];
        callbacks.current.onNavigationUpdate?.({
          ...metrics,
          instruction: firstStep?.maneuver?.instruction ?? null,
          instructionDistance: firstStep ? formatDistance(firstStep.distance) : null,
        });
      })
      .catch(() => {
        // Preserve the last route while the provider or network is unavailable.
      });
    return () => controller.abort();
  }, [orderId, driverLat, driverLng, customerLat, customerLng, navigationMode, ready, drawRoute]);

  const handleRecenter = () => {
    onRecenter?.();
    following.current = true;
    callbacks.current.onFollowModeChange?.(true);
    if (valid(driverLat, driverLng)) {
      map.current?.easeTo({ center: [driverLng!, driverLat!], zoom: NAVIGATION_ZOOM, pitch: NAVIGATION_PITCH, duration: 500 });
    }
  };
  const handleOverview = () => {
    onOverview?.();
    following.current = false;
    callbacks.current.onFollowModeChange?.(false);
    if (valid(driverLat, driverLng) && valid(customerLat, customerLng)) {
      map.current?.fitBounds([[driverLng!, driverLat!], [customerLng!, customerLat!]], { padding: 90, duration: 500 });
    }
  };

  return (
    <div className="fixed inset-0 z-0">
      <div ref={container} className="h-full w-full" />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/25 via-transparent to-black/25" />
      {error && <div className="absolute inset-0 flex items-center justify-center bg-slate-100 p-6 text-center text-sm text-slate-600">Mapa temporariamente indisponível.</div>}
      {ready && !error && <div className="absolute right-3 top-[calc(110px+env(safe-area-inset-top))] z-20 flex flex-col gap-2">
        <button type="button" onClick={handleRecenter} className="h-11 rounded-full bg-white/90 px-4 text-xs font-semibold text-slate-900 shadow-md backdrop-blur">{t("recenter")}</button>
        <button type="button" onClick={handleOverview} className="h-11 rounded-full bg-white/90 px-4 text-xs font-semibold text-slate-900 shadow-md backdrop-blur">{t("overview")}</button>
      </div>}
    </div>
  );
}
