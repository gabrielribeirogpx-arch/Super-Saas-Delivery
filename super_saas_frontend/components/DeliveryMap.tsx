"use client";

import { useEffect, useRef } from "react";
import { getMapboxInstance, getRouteGeometry, LatLng } from "@/lib/mapbox";

function loadMapboxAssets() {
  if (typeof window === "undefined") {
    return Promise.resolve();
  }

  if (window.mapboxgl) {
    return Promise.resolve();
  }

  const cssId = "mapbox-gl-css";
  if (!document.getElementById(cssId)) {
    const link = document.createElement("link");
    link.id = cssId;
    link.rel = "stylesheet";
    link.href = "https://api.mapbox.com/mapbox-gl-js/v3.4.0/mapbox-gl.css";
    document.head.appendChild(link);
  }

  return new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://api.mapbox.com/mapbox-gl-js/v3.4.0/mapbox-gl.js";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Não foi possível carregar o Mapbox GL JS"));
    document.body.appendChild(script);
  });
}

export default function DeliveryMap({
  driverPosition,
  destination,
  drawRoute,
}: {
  driverPosition: LatLng | null;
  destination: LatLng | null;
  drawRoute?: boolean;
}) {
  const mapRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let mounted = true;

    (async () => {
      if (!containerRef.current || mapRef.current) {
        return;
      }

      await loadMapboxAssets();
      const mapboxgl = getMapboxInstance();
      if (!mapboxgl || !mounted) {
        return;
      }

      mapRef.current = new mapboxgl.Map({
        container: containerRef.current,
        style: "mapbox://styles/mapbox/streets-v12",
        center: [-46.6333, -23.5505],
        zoom: 12,
      });
    })();

    return () => {
      mounted = false;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !driverPosition) {
      return;
    }

    const source = map.getSource("driver");
    const data = {
      type: "Feature",
      geometry: { type: "Point", coordinates: [driverPosition.lng, driverPosition.lat] },
      properties: {},
    };

    if (!source) {
      map.addSource("driver", { type: "geojson", data });
      map.addLayer({
        id: "driver",
        type: "circle",
        source: "driver",
        paint: { "circle-radius": 7, "circle-color": "#0f766e" },
      });
      map.flyTo({ center: [driverPosition.lng, driverPosition.lat], zoom: 14 });
      return;
    }

    source.setData(data);
  }, [driverPosition]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !destination) {
      return;
    }

    const source = map.getSource("destination");
    const data = {
      type: "Feature",
      geometry: { type: "Point", coordinates: [destination.lng, destination.lat] },
      properties: {},
    };

    if (!source) {
      map.addSource("destination", { type: "geojson", data });
      map.addLayer({
        id: "destination",
        type: "circle",
        source: "destination",
        paint: { "circle-radius": 7, "circle-color": "#be123c" },
      });
      return;
    }

    source.setData(data);
  }, [destination]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !driverPosition || !destination || !drawRoute) {
      return;
    }

    (async () => {
      const geometry = await getRouteGeometry(driverPosition, destination);
      if (!geometry) {
        return;
      }

      const existing = map.getSource("route");
      const data = { type: "Feature", geometry, properties: {} };

      if (!existing) {
        map.addSource("route", { type: "geojson", data });
        map.addLayer({
          id: "route",
          type: "line",
          source: "route",
          layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": "#2563eb", "line-width": 4 },
        });
        return;
      }

      existing.setData(data);
    })();
  }, [destination, drawRoute, driverPosition]);

  return <div ref={containerRef} className="h-[60vh] w-full rounded-lg" />;
}
