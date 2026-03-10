import type { MapboxConstructor } from "@/lib/maps/types";

export type LatLng = {
  lat: number;
  lng: number;
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
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

  if (!token) {
    return null;
  }

  const coords = `${origin.lng},${origin.lat};${destination.lng},${destination.lat}`;
  const response = await fetch(
    `https://api.mapbox.com/directions/v5/mapbox/driving/${coords}?geometries=geojson&overview=full&access_token=${token}`
  );

  if (!response.ok) {
    return null;
  }

  const data = await response.json();
  return data?.routes?.[0]?.geometry ?? null;
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
