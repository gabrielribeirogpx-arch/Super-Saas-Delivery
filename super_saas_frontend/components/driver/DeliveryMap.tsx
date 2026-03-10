"use client";

import { useEffect, useRef, useState } from "react";
import { geocodeAddress, getMapboxInstance, getRouteData } from "@/lib/mapbox";

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
  customerAddress?: string | null;
  navigationMode?: boolean;
};

function formatDistance(meters: number) {
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(1)} km`;
  }

  return `${Math.round(meters)} m`;
}

function formatEta(seconds: number) {
  const mins = Math.max(1, Math.round(seconds / 60));
  return `${mins} min`;
}

export default function DeliveryMap({
  orderId,
  driverLat,
  driverLng,
  customerLat,
  customerLng,
  customerAddress,
  navigationMode = false,
}: DeliveryMapProps) {
  const mapRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const latestOrderIdRef = useRef(orderId);
  const [destinationCoords, setDestinationCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [distanceRemaining, setDistanceRemaining] = useState<string | null>(null);
  const [etaRemaining, setEtaRemaining] = useState<string | null>(null);

  useEffect(() => {
    latestOrderIdRef.current = orderId;
  }, [orderId]);

  useEffect(() => {
    let cancelled = false;

    const resolveDestination = async () => {
      if (Number.isFinite(customerLat) && Number.isFinite(customerLng)) {
        setDestinationCoords({ lat: customerLat as number, lng: customerLng as number });
        return;
      }

      if (!customerAddress?.trim()) {
        setDestinationCoords(null);
        return;
      }

      const geocoded = await geocodeAddress(customerAddress);
      if (cancelled || latestOrderIdRef.current !== orderId) {
        return;
      }

      setDestinationCoords(geocoded);
    };

    setDestinationCoords(null);
    resolveDestination();

    return () => {
      cancelled = true;
    };
  }, [orderId, customerAddress, customerLat, customerLng]);

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
        style: "mapbox://styles/mapbox/navigation-day-v1",
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
    setDistanceRemaining(null);
    setEtaRemaining(null);
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

    if (navigationMode) {
      map.flyTo({
        center: [driverLng, driverLat],
        zoom: 15,
        pitch: 45,
        bearing: 0,
        essential: true,
      });
    }
  }, [orderId, driverLat, driverLng, navigationMode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !destinationCoords) {
      return;
    }

    const source = map.getSource("customer");
    const data = {
      type: "Feature",
      geometry: { type: "Point", coordinates: [destinationCoords.lng, destinationCoords.lat] },
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
  }, [orderId, destinationCoords]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !Number.isFinite(driverLat) || !Number.isFinite(driverLng) || !destinationCoords) {
      return;
    }

    const currentDriverLat = driverLat as number;
    const currentDriverLng = driverLng as number;
    const currentDestination = destinationCoords;
    let cancelled = false;

    (async () => {
      const routeData = await getRouteData(
        { lat: currentDriverLat, lng: currentDriverLng },
        { lat: currentDestination.lat, lng: currentDestination.lng },
      );
      if (!routeData || cancelled || latestOrderIdRef.current !== orderId) {
        return;
      }

      setDistanceRemaining(formatDistance(routeData.distanceMeters));
      setEtaRemaining(formatEta(routeData.durationSeconds));

      const data = { type: "Feature", geometry: routeData.geometry, properties: {} };
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

    return () => {
      cancelled = true;
    };
  }, [orderId, driverLat, driverLng, destinationCoords]);

  return (
    <div className="relative">
      <div ref={containerRef} className="h-[60vh] w-full rounded-lg border" />
      {navigationMode && etaRemaining && distanceRemaining && (
        <div className="pointer-events-none absolute left-3 top-3 rounded-lg bg-white/95 p-3 text-sm shadow-md">
          <p className="font-semibold text-slate-900">ETA: {etaRemaining}</p>
          <p className="text-slate-700">Distance: {distanceRemaining}</p>
        </div>
      )}
    </div>
  );
}
