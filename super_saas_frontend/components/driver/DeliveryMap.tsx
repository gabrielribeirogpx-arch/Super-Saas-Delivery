"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
  onMetricsChange?: (metrics: { eta: string | null; distance: string | null }) => void;
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
  onMetricsChange,
}: DeliveryMapProps) {
  const mapRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const destinationMarkerRef = useRef<any>(null);
  const driverMarkerRef = useRef<any>(null);
  const latestOrderIdRef = useRef(orderId);
  const lastCoordsRef = useRef<{ lat: number; lng: number } | null>(null);
  const [destinationCoords, setDestinationCoords] = useState<{ lat: number; lng: number } | null>(null);

  const buildDriverMarker = useCallback(() => {
    const marker = document.createElement("div");
    marker.className = "flex h-10 w-10 items-center justify-center rounded-full border-2 border-white bg-blue-600 text-lg text-white shadow-lg";
    marker.textContent = "🛵";
    return marker;
  }, []);

  const buildCustomerMarker = useCallback(() => {
    const marker = document.createElement("div");
    marker.className = "flex h-9 w-9 items-center justify-center rounded-full border-2 border-white bg-rose-600 text-base text-white shadow-lg";
    marker.textContent = "📍";
    return marker;
  }, []);

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
        style: "mapbox://styles/mapbox/standard",
        center: [-46.6333, -23.5505],
        zoom: 12,
        pitch: 60,
        bearing: 0,
      });

      mapRef.current.addControl(new mapboxgl.NavigationControl(), "top-right");
    })();

    return () => {
      mounted = false;
      destinationMarkerRef.current?.remove();
      driverMarkerRef.current?.remove();
      mapRef.current?.remove();
      destinationMarkerRef.current = null;
      driverMarkerRef.current = null;
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const layerIds = ["route", "route-shadow"];
    const sourceIds = ["route"];

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

    destinationMarkerRef.current?.remove();
    driverMarkerRef.current?.remove();
    destinationMarkerRef.current = null;
    driverMarkerRef.current = null;
    onMetricsChange?.({ eta: null, distance: null });
    lastCoordsRef.current = null;
  }, [orderId, onMetricsChange]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !Number.isFinite(driverLat) || !Number.isFinite(driverLng)) {
      return;
    }

    const currentCoords: [number, number] = [driverLng as number, driverLat as number];

    if (!driverMarkerRef.current) {
      const mapboxgl = getMapboxInstance();
      if (!mapboxgl) {
        return;
      }

      driverMarkerRef.current = new mapboxgl.Marker({ element: buildDriverMarker() }).setLngLat(currentCoords).addTo(map);
      map.easeTo({ center: currentCoords, zoom: 15, duration: 600 });
    } else {
      driverMarkerRef.current.setLngLat(currentCoords);
    }

    const previous = lastCoordsRef.current;
    const heading = previous
      ? ((Math.atan2(currentCoords[0] - previous.lng, currentCoords[1] - previous.lat) * 180) / Math.PI + 360) % 360
      : 0;

    if (navigationMode) {
      map.flyTo({
        center: currentCoords,
        zoom: 16,
        pitch: 60,
        bearing: heading,
        speed: 0.8,
        essential: true,
      });
    }

    lastCoordsRef.current = { lat: currentCoords[1], lng: currentCoords[0] };
  }, [driverLat, driverLng, navigationMode, buildDriverMarker]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !destinationCoords) {
      return;
    }

    const target: [number, number] = [destinationCoords.lng, destinationCoords.lat];

    if (!destinationMarkerRef.current) {
      const mapboxgl = getMapboxInstance();
      if (!mapboxgl) {
        return;
      }

      destinationMarkerRef.current = new mapboxgl.Marker({ element: buildCustomerMarker() }).setLngLat(target).addTo(map);
      return;
    }

    destinationMarkerRef.current.setLngLat(target);
  }, [destinationCoords, buildCustomerMarker]);

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

      onMetricsChange?.({
        eta: formatEta(routeData.durationSeconds),
        distance: formatDistance(routeData.distanceMeters),
      });

      const data = { type: "Feature", geometry: routeData.geometry, properties: {} };
      const source = map.getSource("route");

      if (!source) {
        map.addSource("route", { type: "geojson", data });
        map.addLayer({
          id: "route-shadow",
          type: "line",
          source: "route",
          layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": "rgba(0,0,0,0.15)", "line-width": 10 },
        });
        map.addLayer({
          id: "route",
          type: "line",
          source: "route",
          layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": "#007AFF", "line-width": 6, "line-opacity": 0.9 },
        });
      } else {
        source.setData(data);
      }

      if (!navigationMode) {
        const coordinates = routeData.geometry.coordinates as [number, number][];
        const lngs = coordinates.map((coord) => coord[0]);
        const lats = coordinates.map((coord) => coord[1]);
        map.fitBounds(
          [
            [Math.min(...lngs), Math.min(...lats)],
            [Math.max(...lngs), Math.max(...lats)],
          ],
          { padding: 70, duration: 600 },
        );
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [orderId, driverLat, driverLng, destinationCoords, navigationMode, onMetricsChange]);

  const handleRecenter = () => {
    if (!mapRef.current || !Number.isFinite(driverLat) || !Number.isFinite(driverLng)) {
      return;
    }

    mapRef.current.flyTo({
      center: [driverLng, driverLat],
      zoom: 16,
      pitch: 60,
      speed: 0.8,
      essential: true,
    });
  };

  const handleOverview = () => {
    const map = mapRef.current;
    const routeSource = map?.getSource("route");
    if (!map || !routeSource || !Number.isFinite(driverLat) || !Number.isFinite(driverLng) || !destinationCoords) {
      return;
    }

    const currentDriverLng = driverLng as number;
    const currentDriverLat = driverLat as number;

    map.fitBounds(
      [
        [Math.min(currentDriverLng, destinationCoords.lng), Math.min(currentDriverLat, destinationCoords.lat)],
        [Math.max(currentDriverLng, destinationCoords.lng), Math.max(currentDriverLat, destinationCoords.lat)],
      ],
      { padding: 90, duration: 700 },
    );
  };

  return (
    <div className="fixed inset-0 z-0">
      <div ref={containerRef} className="h-full w-full" />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/25 via-transparent to-black/25" />
      <div className="absolute bottom-36 right-3 z-20 flex flex-col gap-2">
        <button
          type="button"
          onClick={handleRecenter}
          className="rounded-full bg-white px-3 py-2 text-xs font-semibold text-slate-900 shadow-md"
        >
          RECENTER
        </button>
        <button
          type="button"
          onClick={handleOverview}
          className="rounded-full bg-white px-3 py-2 text-xs font-semibold text-slate-900 shadow-md"
        >
          OVERVIEW
        </button>
      </div>
    </div>
  );
}
