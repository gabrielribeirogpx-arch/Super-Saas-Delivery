"use client";

import { useEffect, useRef, useState } from "react";
import { createMapInstance } from "@/lib/maps/mapInstance";
import type { MapboxMap, MapboxMarker } from "@/lib/maps/types";

type LatLng = {
  lat: number;
  lng: number;
};

type CustomerTrackingMapProps = {
  orderId: string;
  driverLocation: LatLng | null;
  customerLocation: LatLng;
};

const TEST_CENTER: LatLng = {
  lat: -23.5505,
  lng: -46.6333,
};

function createMarkerElement(className: string): HTMLDivElement {
  const el = document.createElement("div");
  el.className = className;
  return el;
}

export default function CustomerTrackingMap({ orderId }: CustomerTrackingMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapboxMap | null>(null);
  const markerRef = useRef<MapboxMarker | null>(null);
  const initializedRef = useRef(false);
  const [showIframeFallback, setShowIframeFallback] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    let isMounted = true;

    const initMap = async () => {
      if (initializedRef.current) return;
      initializedRef.current = true;

      console.log("Initializing map...");
      console.log("Map container:", containerRef.current);
      console.log("Window:", typeof window);
      console.log("[tracking] order id:", orderId);

      if (!containerRef.current) {
        console.error("Tracking map container is unavailable.");
        initializedRef.current = false;
        setShowIframeFallback(true);
        return;
      }

      console.log("Map container height:", containerRef.current.offsetHeight);

      if (containerRef.current.offsetHeight === 0) {
        console.error("Map container has zero height");
      }

      try {
        const map = await createMapInstance({
          container: containerRef.current,
          center: [TEST_CENTER.lng, TEST_CENTER.lat],
          zoom: 13,
          pitch: 0,
          bearing: 0,
          style: "mapbox://styles/mapbox/streets-v12",
        });

        if (!isMounted) {
          map.remove();
          return;
        }

        mapRef.current = map;

        setTimeout(() => {
          map.resize();
        }, 300);

        markerRef.current = new window.mapboxgl!.Marker({
          element: createMarkerElement("h-5 w-5 rounded-full border-2 border-white bg-emerald-500 shadow-md"),
        })
          .setLngLat([TEST_CENTER.lng, TEST_CENTER.lat])
          .addTo(map);
      } catch (error) {
        console.error("Map initialization failed", error);
        initializedRef.current = false;
        setShowIframeFallback(true);
      }
    };

    void initMap();

    return () => {
      isMounted = false;
      markerRef.current?.remove();
      mapRef.current?.remove();
      mapRef.current = null;
      initializedRef.current = false;
    };
  }, [orderId]);

  if (showIframeFallback) {
    return (
      <iframe
        title="Tracking map fallback"
        className="h-[420px] w-full overflow-hidden rounded-2xl border border-slate-200"
        src="https://www.openstreetmap.org/export/embed.html?bbox=-46.72%2C-23.62%2C-46.55%2C-23.49&layer=mapnik&marker=-23.5505%2C-46.6333"
      />
    );
  }

  return (
    <div
      ref={containerRef}
      id="tracking-map"
      style={{
        width: "100%",
        height: "50vh",
        minHeight: "300px",
      }}
      className="overflow-hidden rounded-2xl"
    />
  );
}
