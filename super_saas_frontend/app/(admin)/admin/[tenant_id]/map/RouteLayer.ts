import { getMapboxAccessToken } from "@/lib/maps/mapInstance";
import type { Feature, LineString } from "geojson";
import type { LngLatTuple, MapboxGeoJSONSource, MapboxMap } from "@/lib/maps/types";

const ROUTE_SOURCE_ID = "route";
const ROUTE_LAYER_GLOW_ID = "route-line-glow";
const ROUTE_LAYER_MAIN_ID = "route-line-main";

interface DirectionsResponse {
  routes?: Array<{ geometry?: { coordinates: number[][] } }>;
}

export type RouteGeometry = Feature<LineString>;

export function ensureRouteLayer(map: MapboxMap): void {
  if (!map.getSource(ROUTE_SOURCE_ID)) {
    map.addSource(ROUTE_SOURCE_ID, {
      type: "geojson",
      data: {
        type: "Feature",
        geometry: { type: "LineString", coordinates: [] },
        properties: {},
      },
    });
  }

  if (!map.getLayer(ROUTE_LAYER_GLOW_ID)) {
    map.addLayer({
      id: ROUTE_LAYER_GLOW_ID,
      type: "line",
      source: ROUTE_SOURCE_ID,
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#6366f1", "line-width": 14, "line-opacity": 0.25 },
    });
  }

  if (!map.getLayer(ROUTE_LAYER_MAIN_ID)) {
    map.addLayer({
      id: ROUTE_LAYER_MAIN_ID,
      type: "line",
      source: ROUTE_SOURCE_ID,
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#6366f1", "line-width": 6, "line-opacity": 0.95 },
    });
  }
}

export async function fetchRoute(map: MapboxMap, origin: LngLatTuple, destination: LngLatTuple): Promise<RouteGeometry | null> {
  const token = getMapboxAccessToken();
  if (!token) return null;

  const [originLng, originLat] = origin;
  const [destinationLng, destinationLat] = destination;

  const response = await fetch(
    `https://api.mapbox.com/directions/v5/mapbox/driving/${originLng},${originLat};${destinationLng},${destinationLat}?geometries=geojson&overview=full&access_token=${encodeURIComponent(token)}`,
  );
  if (!response.ok) return null;

  const data = (await response.json()) as DirectionsResponse;
  const coordinates = data.routes?.[0]?.geometry?.coordinates;
  if (!coordinates || coordinates.length < 2) return null;

  const routeFeature: RouteGeometry = {
    type: "Feature",
    properties: {},
    geometry: { type: "LineString", coordinates },
  };

  const source = map.getSource(ROUTE_SOURCE_ID) as MapboxGeoJSONSource | undefined;
  source?.setData(routeFeature);

  return routeFeature;
}
