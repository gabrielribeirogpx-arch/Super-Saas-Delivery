import type { MapboxConstructor } from "@/lib/maps/types";

export type LatLng = {
  lat: number;
  lng: number;
};

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
