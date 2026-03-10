"use client";

import { useEffect, useRef } from "react";
import { getMapboxInstance, getRouteGeometry } from "@/lib/mapbox";

function loadMapboxAssets() {
  if (typeof window === "undefined" || window.mapboxgl) {
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
    script.onerror = () => reject(new Error("Failed to load Mapbox GL JS"));
    document.body.appendChild(script);
  });
}

type DeliveryMapProps = {
  orderId: number;
  driverLat?: number | null;
  driverLng?: number | null;
  customerLat?: number | null;
  customerLng?: number | null;
};

export default function DeliveryMap({ orderId, driverLat, driverLng, customerLat, customerLng }: DeliveryMapProps) {
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
    if (!map) {
      return;
    }

    const layerIds = ["route", "driver", "customer"];
    const sourceIds = ["route", "driver", "customer"];

    for (const layerId of layerIds) {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId);
      }
    }

    for (const sourceId of sourceIds) {
      if (map.getSource(sourceId)) {
        map.removeSource(sourceId);
      }
    }
  }, [orderId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !Number.isFinite(driverLat) || !Number.isFinite(driverLng)) {
      return;
    }

    const source = map.getSource("driver");
    const data = {
      type: "Feature",
      geometry: { type: "Point", coordinates: [driverLng, driverLat] },
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
      map.easeTo({ center: [driverLng, driverLat], zoom: 14, duration: 600 });
      return;
    }

    source.setData(data);
  }, [orderId, driverLat, driverLng]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !Number.isFinite(customerLat) || !Number.isFinite(customerLng)) {
      return;
    }

    const source = map.getSource("customer");
    const data = {
      type: "Feature",
      geometry: { type: "Point", coordinates: [customerLng, customerLat] },
      properties: {},
    };

    if (!source) {
      map.addSource("customer", { type: "geojson", data });
      map.addLayer({
        id: "customer",
        type: "circle",
        source: "customer",
        paint: { "circle-radius": 7, "circle-color": "#be123c" },
      });
      return;
    }

    source.setData(data);
  }, [orderId, customerLat, customerLng]);

  useEffect(() => {
    const map = mapRef.current;
    if (
      !map ||
      !Number.isFinite(driverLat) ||
      !Number.isFinite(driverLng) ||
      !Number.isFinite(customerLat) ||
      !Number.isFinite(customerLng)
    ) {
      return;
    }

    const currentDriverLat = driverLat as number;
    const currentDriverLng = driverLng as number;
    const currentCustomerLat = customerLat as number;
    const currentCustomerLng = customerLng as number;

    (async () => {
      const geometry = await getRouteGeometry(
        { lat: currentDriverLat, lng: currentDriverLng },
        { lat: currentCustomerLat, lng: currentCustomerLng },
      );
      if (!geometry) {
        return;
      }

      const data = { type: "Feature", geometry, properties: {} };
      const source = map.getSource("route");
      if (!source) {
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

      source.setData(data);
    })();
  }, [orderId, driverLat, driverLng, customerLat, customerLng]);

  return <div ref={containerRef} className="h-[60vh] w-full rounded-lg border" />;
}
