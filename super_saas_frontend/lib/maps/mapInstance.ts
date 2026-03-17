import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

import type { LngLatTuple, MapboxMap } from "./types";

export interface MapInstanceOptions {
  container: HTMLElement | string;
  center?: LngLatTuple;
  zoom?: number;
  style?: string;
  pitch?: number;
  bearing?: number;
}

function resolveMapboxToken(): string {
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN as string;
  const safeToken = token || "";
  if (!safeToken) {
    throw new Error("Mapbox token ausente. Defina NEXT_PUBLIC_MAPBOX_TOKEN.");
  }
  return safeToken;
}

export async function createMapInstance({
  container,
  center = [-51.9253, -14.235],
  zoom = 4,
  style = "mapbox://styles/mapbox/navigation-day-v1",
  pitch = 40,
  bearing = -10,
}: MapInstanceOptions): Promise<MapboxMap> {
  mapboxgl.accessToken = resolveMapboxToken();
  window.mapboxgl = mapboxgl;

  return new mapboxgl.Map({
    container,
    style,
    center,
    zoom,
    pitch,
    bearing,
    attributionControl: true,
  }) as MapboxMap;
}

export function getMapboxAccessToken(): string {
  return mapboxgl.accessToken ?? "";
}
