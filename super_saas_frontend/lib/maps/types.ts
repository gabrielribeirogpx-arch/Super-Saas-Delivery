export type LngLatTuple = [number, number];

export interface MapboxGeoJSONSource {
  setData: (data: GeoJSON.GeoJSON) => void;
}

export interface MapboxMap {
  on: (event: "load", handler: () => void) => void;
  addSource: (id: string, source: Record<string, unknown>) => void;
  getSource: (id: string) => MapboxGeoJSONSource | undefined;
  addLayer: (layer: Record<string, unknown>) => void;
  getLayer: (id: string) => Record<string, unknown> | undefined;
  easeTo: (options: { center?: LngLatTuple; zoom?: number; duration?: number }) => void;
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
}

declare global {
  interface Window {
    mapboxgl?: MapboxConstructor;
  }
}
