import type { GeoJsonObject } from "geojson";

export type LngLatTuple = [number, number];

export interface MapboxGeoJSONSource {
  setData: (data: GeoJsonObject) => void;
}

export interface MapboxMap {
  on: (event: "load", handler: () => void) => void;
  addSource: (id: string, source: Record<string, unknown>) => void;
  getSource: (id: string) => MapboxGeoJSONSource | undefined;
  addLayer: (layer: Record<string, unknown>) => void;
  getLayer: (id: string) => Record<string, unknown> | undefined;
  removeLayer: (id: string) => void;
  removeSource: (id: string) => void;
  setFog: (fog: Record<string, unknown>) => void;
  addControl: (control: unknown, position?: string) => void;
  easeTo: (options: { center?: LngLatTuple; zoom?: number; pitch?: number; bearing?: number; duration?: number }) => void;
  flyTo: (options: {
    center?: LngLatTuple;
    zoom?: number;
    pitch?: number;
    bearing?: number;
    speed?: number;
    essential?: boolean;
  }) => void;
  fitBounds: (bounds: [LngLatTuple, LngLatTuple], options?: { padding?: number; duration?: number }) => void;
  resize: () => void;
  remove: () => void;
}

export interface MapboxMarker {
  setLngLat: (position: LngLatTuple) => MapboxMarker;
  getLngLat: () => { lng: number; lat: number };
  addTo: (map: MapboxMap) => MapboxMarker;
  remove: () => void;
  getElement: () => HTMLElement;
}

export interface MapboxConstructor {
  accessToken: string;
  Map: new (options: Record<string, unknown>) => MapboxMap;
  Marker: new (options: { element: HTMLElement }) => MapboxMarker;
  NavigationControl: new () => unknown;
}

declare global {
  interface Window {
    mapboxgl?: MapboxConstructor;
  }
}
