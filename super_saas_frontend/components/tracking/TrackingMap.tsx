"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import mapboxgl, { type GeoJSONSource, type LngLatBoundsLike, type Map as MapboxMap, type Marker } from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { TrackingAnimator } from "@/lib/maps/trackingAnimator";

type LatLng = { lat: number; lng: number };
type TrackingState = {
  destinationLat?: number | null;
  destinationLng?: number | null;
  driverLat?: number | null;
  driverLng?: number | null;
  hasDriverLocation?: boolean;
} | null;
type Props = {
  tracking: TrackingState;
  destination: LatLng | null;
  isOutForDelivery: boolean;
  fullScreen?: boolean;
  containerClassName?: string;
};

const TOKEN = process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN?.trim()
  || process.env.NEXT_PUBLIC_MAPBOX_TOKEN?.trim() || "";
const FALLBACK_CENTER: LatLng = { lat: -23.5505, lng: -46.6333 };
const ROUTE_SOURCE = "delivery-route";
const ROUTE_LAYER = "delivery-route-line";
const DESKTOP_BREAKPOINT = 900;

function cameraOffset(): [number, number] {
  return window.innerWidth >= DESKTOP_BREAKPOINT ? [-190, 0] : [0, 0];
}

function routePadding() {
  return window.innerWidth >= DESKTOP_BREAKPOINT
    ? { top: 72, bottom: 72, left: 72, right: 452 }
    : 56;
}

function valid(point: LatLng | null): point is LatLng {
  return !!point && Number.isFinite(point.lat) && Number.isFinite(point.lng)
    && Math.abs(point.lat) <= 90 && Math.abs(point.lng) <= 180;
}

function markerElement(kind: "driver" | "destination") {
  const element = document.createElement("div");
  element.className = kind === "driver" ? "delivery-driver-marker" : "delivery-destination-marker";
  element.setAttribute("role", "img");
  element.setAttribute("aria-label", kind === "driver" ? "Posição do entregador" : "Destino da entrega");
  element.style.cssText = kind === "driver"
    ? "width:38px;height:38px;border:4px solid white;border-radius:50%;background:#cf0714;box-shadow:0 3px 12px #11182788;"
    : "width:24px;height:24px;border:5px solid white;border-radius:50%;background:#16a34a;box-shadow:0 3px 10px #11182777;";
  return element;
}

function routeGeoJSON(coordinates: number[][]): Parameters<GeoJSONSource["setData"]>[0] {
  return coordinates.length < 2
    ? { type: "FeatureCollection", features: [] }
    : {
      type: "Feature",
      properties: {},
      geometry: { type: "LineString", coordinates },
    } as Parameters<GeoJSONSource["setData"]>[0];
}

async function fetchRoute(origin: LatLng, destination: LatLng, signal: AbortSignal): Promise<number[][]> {
  const coords = `${origin.lng},${origin.lat};${destination.lng},${destination.lat}`;
  const url = new URL(`https://api.mapbox.com/directions/v5/mapbox/driving/${coords}`);
  url.searchParams.set("access_token", TOKEN);
  url.searchParams.set("geometries", "geojson");
  url.searchParams.set("overview", "full");
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`Mapbox directions: ${response.status}`);
  const data = await response.json();
  if (data.code !== "Ok") throw new Error("Route unavailable");
  const coordinates = data.routes?.[0]?.geometry?.coordinates;
  return Array.isArray(coordinates) && coordinates.length >= 2 ? coordinates : [];
}

export default function TrackingMap({ tracking, destination, isOutForDelivery, fullScreen = false, containerClassName = "" }: Props) {
  const destinationPoint = useMemo(() => {
    const lat = tracking?.destinationLat ?? destination?.lat;
    const lng = tracking?.destinationLng ?? destination?.lng;
    const point = lat == null || lng == null ? null : { lat: Number(lat), lng: Number(lng) };
    return valid(point) ? point : null;
  }, [tracking?.destinationLat, tracking?.destinationLng, destination?.lat, destination?.lng]);
  const driverPoint = useMemo(() => {
    const lat = tracking?.driverLat;
    const lng = tracking?.driverLng;
    const point = lat == null || lng == null ? null : { lat: Number(lat), lng: Number(lng) };
    return valid(point) && tracking?.hasDriverLocation && isOutForDelivery ? point : null;
  }, [tracking?.driverLat, tracking?.driverLng, tracking?.hasDriverLocation, isOutForDelivery]);

  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapboxMap | null>(null);
  const driverMarker = useRef<Marker | null>(null);
  const destinationMarker = useRef<Marker | null>(null);
  const animator = useRef<TrackingAnimator | null>(null);
  const lastDriver = useRef<LatLng | null>(null);
  const lastRouteKey = useRef("");
  const lastRouteAt = useRef(0);
  const routeAbort = useRef<AbortController | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!container.current) return;
    if (!TOKEN || !TOKEN.startsWith("pk.")) {
      setError("Mapa temporariamente indisponível. O status do pedido continua sendo atualizado.");
      return;
    }
    setError(null);
    mapboxgl.accessToken = TOKEN;
    const instance = new mapboxgl.Map({
      container: container.current,
      style: "mapbox://styles/mapbox/streets-v12",
      center: [FALLBACK_CENTER.lng, FALLBACK_CENTER.lat],
      zoom: 15,
      attributionControl: true,
    });
    map.current = instance;
    instance.on("load", () => {
      instance.addSource(ROUTE_SOURCE, { type: "geojson", data: routeGeoJSON([]) });
      instance.addLayer({
        id: ROUTE_LAYER,
        type: "line",
        source: ROUTE_SOURCE,
        paint: { "line-color": "#cf0714", "line-width": 5, "line-opacity": 0.88 },
        layout: { "line-cap": "round", "line-join": "round" },
      });
      setMapReady(true);
    });
    instance.on("error", () => setError("Não foi possível carregar o mapa agora."));
    return () => {
      routeAbort.current?.abort();
      animator.current?.cancel();
      driverMarker.current?.remove();
      destinationMarker.current?.remove();
      driverMarker.current = null;
      destinationMarker.current = null;
      map.current = null;
      instance.remove();
    };
  }, [Boolean(destinationPoint || driverPoint)]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !mapReady) return;
    if (!destinationPoint) {
      destinationMarker.current?.remove();
      destinationMarker.current = null;
      return;
    }
    const coordinate: [number, number] = [destinationPoint.lng, destinationPoint.lat];
    if (!destinationMarker.current) {
      destinationMarker.current = new mapboxgl.Marker({ element: markerElement("destination") })
        .setLngLat(coordinate).addTo(instance);
    } else {
      destinationMarker.current.setLngLat(coordinate);
    }
    if (!driverPoint) instance.easeTo({ center: coordinate, offset: cameraOffset(), duration: 500 });
  }, [destinationPoint, driverPoint, mapReady]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !mapReady) return;
    if (!driverPoint) {
      animator.current?.cancel();
      driverMarker.current?.remove();
      driverMarker.current = null;
      lastDriver.current = null;
      return;
    }
    const coordinate: [number, number] = [driverPoint.lng, driverPoint.lat];
    if (!driverMarker.current) {
      driverMarker.current = new mapboxgl.Marker({ element: markerElement("driver") })
        .setLngLat(coordinate).addTo(instance);
      animator.current = new TrackingAnimator({
        setPosition: ([lng, lat]) => driverMarker.current?.setLngLat([lng, lat]),
      });
    } else if (lastDriver.current) {
      animator.current?.animate(
        [lastDriver.current.lng, lastDriver.current.lat], coordinate,
      );
    }
    lastDriver.current = driverPoint;
    instance.easeTo({ center: coordinate, offset: cameraOffset(), duration: 600 });
  }, [driverPoint, mapReady]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !mapReady) return;
    const source = instance.getSource(ROUTE_SOURCE) as GeoJSONSource | undefined;
    if (!source) return;
    if (!isOutForDelivery || !driverPoint || !destinationPoint) {
      routeAbort.current?.abort();
      source.setData(routeGeoJSON([]));
      lastRouteKey.current = "";
      return;
    }
    const key = `${driverPoint.lat.toFixed(5)},${driverPoint.lng.toFixed(5)}:${destinationPoint.lat.toFixed(5)},${destinationPoint.lng.toFixed(5)}`;
    if (key === lastRouteKey.current || Date.now() - lastRouteAt.current < 30_000) return;
    routeAbort.current?.abort();
    const controller = new AbortController();
    routeAbort.current = controller;
    lastRouteKey.current = key;
    lastRouteAt.current = Date.now();
    void fetchRoute(driverPoint, destinationPoint, controller.signal)
      .then((coordinates) => {
        if (controller.signal.aborted) return;
        source.setData(routeGeoJSON(coordinates));
        if (coordinates.length > 1) {
          const bounds = coordinates.reduce(
            (current, point) => current.extend([point[0], point[1]]),
            new mapboxgl.LngLatBounds(
              [driverPoint.lng, driverPoint.lat],
              [driverPoint.lng, driverPoint.lat],
            ),
          );
          instance.fitBounds(bounds as LngLatBoundsLike, { padding: routePadding(), maxZoom: 16, duration: 500 });
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) source.setData(routeGeoJSON([]));
      });
    return () => controller.abort();
  }, [destinationPoint, driverPoint, isOutForDelivery, mapReady]);

  const empty = !destinationPoint && !driverPoint;
  const className = fullScreen
    ? "relative min-h-0 w-full flex-1 overflow-hidden bg-slate-100"
    : "relative w-full overflow-hidden rounded-2xl border border-slate-200 bg-slate-100 shadow-sm";
  if (empty) {
    return <div className={`${className} ${containerClassName} flex items-center justify-center p-6 text-center text-sm text-slate-600`}>Aguardando a localização da entrega.</div>;
  }
  return (
    <div className={`${className} ${containerClassName}`}>
      <div ref={container} className={fullScreen ? "h-full w-full" : "h-[360px] w-full"} />
      {error && <div className="absolute inset-0 flex items-center justify-center bg-slate-100 p-6 text-center text-sm text-slate-600">{error}</div>}
      {!error && isOutForDelivery && !driverPoint && <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-slate-950/10"><div className="rounded-full bg-white px-4 py-2 text-sm shadow-lg">Atualizando posição do entregador</div></div>}
      {!fullScreen && !error && <div className="pointer-events-none absolute bottom-3 left-3 rounded-full bg-white/90 px-3 py-1 text-[11px] shadow-sm">{driverPoint ? "Posição do entregador" : "Mapa da entrega"}</div>}
    </div>
  );
}
