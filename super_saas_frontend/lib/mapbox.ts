import type { MapboxConstructor } from "@/lib/maps/types";

export type LatLng = {
  lat: number;
  lng: number;
};

export type RouteData = {
  geometry: { type: "LineString"; coordinates: number[][] };
  distanceMeters: number;
  durationSeconds: number;
  steps: Array<Record<string, unknown>>;
};

export function buildBrazilAddressQuery(address: string) {
  const normalized = address.trim();
  if (!normalized) {
    return "";
  }

  if (/\bbrasil\b|\bbrazil\b/i.test(normalized)) {
    return normalized;
  }

  return `${normalized} Brazil`;
}

export function getMapboxInstance(): MapboxConstructor | null {
  if (typeof window === "undefined") {
    return null;
  }

  if (window.mapboxgl) {
    window.mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || "";
  }

  return window.mapboxgl || null;
}

export async function getRouteGeometry(origin: LatLng, destination: LatLng) {
  const route = await getRouteData(origin, destination);
  return route?.geometry ?? null;
}

export async function getRouteData(origin: LatLng, destination: LatLng): Promise<RouteData | null> {
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

  if (!token) {
    return null;
  }

  const coords = `${origin.lng},${origin.lat};${destination.lng},${destination.lat}`;
  const response = await fetch(
    `https://api.mapbox.com/directions/v5/mapbox/driving/${coords}?geometries=geojson&overview=full&steps=true&access_token=${token}`
  );

  if (!response.ok) {
    return null;
  }

  const data = await response.json();
  const route = data?.routes?.[0];
  const geometry = route?.geometry;
  const distanceMeters = route?.distance;
  const durationSeconds = route?.duration;
  const steps = route?.legs?.[0]?.steps;

  if (
    !geometry ||
    geometry.type !== "LineString" ||
    !Array.isArray(geometry.coordinates) ||
    !Number.isFinite(distanceMeters) ||
    !Number.isFinite(durationSeconds) ||
    !Array.isArray(steps)
  ) {
    return null;
  }

  return {
    geometry,
    distanceMeters,
    durationSeconds,
    steps,
  };
}

export async function geocodeAddress(address: string): Promise<LatLng | null> {
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
  const query = buildBrazilAddressQuery(address);

  if (!token || !query) {
    return null;
  }

  const encodedAddress = encodeURIComponent(query);
  const response = await fetch(
    `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodedAddress}.json?access_token=${token}&country=BR&limit=1`
  );

  if (!response.ok) {
    return null;
  }

  const data = await response.json();
  const center = data?.features?.[0]?.center;

  if (!Array.isArray(center) || !Number.isFinite(center[0]) || !Number.isFinite(center[1])) {
    return null;
  }

  return { lng: center[0], lat: center[1] };
}

export async function snapPositionToRoad(position: LatLng, previousPosition?: LatLng | null): Promise<LatLng | null> {
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

  if (!token) {
    return null;
  }

  const waypoints = previousPosition
    ? `${previousPosition.lng},${previousPosition.lat};${position.lng},${position.lat}`
    : `${position.lng},${position.lat}`;
  const radiuses = previousPosition ? "25;25" : "25";
  const response = await fetch(
    `https://api.mapbox.com/matching/v5/mapbox/driving/${waypoints}?geometries=geojson&overview=full&steps=false&tidy=true&radiuses=${radiuses}&access_token=${token}`
  ).catch(() => null);

  if (!response?.ok) {
    return null;
  }

  const data = await response.json();
  const tracepoints = Array.isArray(data?.tracepoints) ? data.tracepoints : [];
  const lastTracepoint = tracepoints[tracepoints.length - 1];
  const coordinates = lastTracepoint?.location;

  if (!Array.isArray(coordinates) || !Number.isFinite(coordinates[0]) || !Number.isFinite(coordinates[1])) {
    return null;
  }

  return { lng: coordinates[0], lat: coordinates[1] };
}
