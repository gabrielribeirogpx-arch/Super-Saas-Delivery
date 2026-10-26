declare module "geojson" {
  export interface GeometryObject {
    type: string;
    bbox?: number[];
  }

  export interface Point extends GeometryObject {
    type: "Point";
    coordinates: [number, number] | [number, number, number];
  }

  export interface LineString extends GeometryObject {
    type: "LineString";
    coordinates: number[][];
  }

  export type Geometry = Point | LineString;

  export interface Feature<G extends Geometry | null = Geometry, P = Record<string, unknown>> {
    type: "Feature";
    geometry: G;
    properties: P;
    id?: string | number;
    bbox?: number[];
  }

  export interface FeatureCollection<G extends Geometry | null = Geometry, P = Record<string, unknown>> {
    type: "FeatureCollection";
    features: Array<Feature<G, P>>;
    bbox?: number[];
  }

  export type GeoJsonObject = Geometry | Feature | FeatureCollection;
}
