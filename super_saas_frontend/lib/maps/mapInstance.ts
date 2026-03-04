import type { LngLatTuple, MapboxConstructor, MapboxMap } from "./types";

const MAPBOX_SCRIPT_ID = "mapbox-gl-js";
const MAPBOX_CSS_ID = "mapbox-gl-css";

type ImportMetaEnv = {
  VITE_MAPBOX_TOKEN?: string;
};

export interface MapInstanceOptions {
  container: HTMLElement;
  center?: LngLatTuple;
  zoom?: number;
}

function resolveMapboxToken(): string {
  const importMetaEnv = (import.meta as ImportMeta & { env?: ImportMetaEnv }).env;
  const token = importMetaEnv?.VITE_MAPBOX_TOKEN ?? process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";
  if (!token) {
    throw new Error("Mapbox token ausente. Defina VITE_MAPBOX_TOKEN.");
  }
  return token;
}

function ensureMapboxAssets(): Promise<MapboxConstructor> {
  return new Promise((resolve, reject) => {
    if (window.mapboxgl) {
      resolve(window.mapboxgl);
      return;
    }

    if (!document.getElementById(MAPBOX_CSS_ID)) {
      const css = document.createElement("link");
      css.id = MAPBOX_CSS_ID;
      css.rel = "stylesheet";
      css.href = "https://api.mapbox.com/mapbox-gl-js/v3.5.2/mapbox-gl.css";
      document.head.appendChild(css);
    }

    const existingScript = document.getElementById(MAPBOX_SCRIPT_ID) as HTMLScriptElement | null;
    if (existingScript) {
      existingScript.addEventListener("load", () => {
        if (window.mapboxgl) resolve(window.mapboxgl);
      });
      existingScript.addEventListener("error", () => reject(new Error("Falha ao carregar mapbox-gl.")));
      return;
    }

    const script = document.createElement("script");
    script.id = MAPBOX_SCRIPT_ID;
    script.src = "https://api.mapbox.com/mapbox-gl-js/v3.5.2/mapbox-gl.js";
    script.async = true;
    script.onload = () => {
      if (window.mapboxgl) {
        resolve(window.mapboxgl);
      } else {
        reject(new Error("Mapbox GL indisponível após carregamento."));
      }
    };
    script.onerror = () => reject(new Error("Falha ao carregar mapbox-gl."));
    document.body.appendChild(script);
  });
}

export async function createMapInstance({ container, center = [-51.9253, -14.235], zoom = 4 }: MapInstanceOptions): Promise<MapboxMap> {
  const mapboxgl = await ensureMapboxAssets();
  mapboxgl.accessToken = resolveMapboxToken();
  return new mapboxgl.Map({
    container,
    style: "mapbox://styles/mapbox/streets-v12",
    center,
    zoom,
    attributionControl: true,
  });
}

export function getMapboxAccessToken(): string {
  return window.mapboxgl?.accessToken ?? "";
}
