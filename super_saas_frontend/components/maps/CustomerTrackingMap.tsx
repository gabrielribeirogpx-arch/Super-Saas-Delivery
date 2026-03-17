"use client";

import { useEffect, useRef } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

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

const DRIVER_SOURCE_ID = "tracking-driver-line";
const DRIVER_LAYER_ID = "tracking-driver-line-layer";

function parseIncomingDriverPosition(payload: unknown): LatLng | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const candidate = payload as {
    lat?: unknown;
    lng?: unknown;
    driver_lat?: unknown;
    driver_lng?: unknown;
    location?: { lat?: unknown; lng?: unknown };
    driver_location?: { lat?: unknown; lng?: unknown };
  };

  const lat = Number(candidate.lat ?? candidate.driver_lat ?? candidate.location?.lat ?? candidate.driver_location?.lat);
  const lng = Number(candidate.lng ?? candidate.driver_lng ?? candidate.location?.lng ?? candidate.driver_location?.lng);

  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return null;
  }

  return { lat, lng };
}

function createMarkerElement(className: string): HTMLDivElement {
  const el = document.createElement("div");
  el.className = className;
  return el;
}

export default function CustomerTrackingMap({ orderId, driverLocation, customerLocation }: CustomerTrackingMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapboxMap | null>(null);
  const customerMarkerRef = useRef<MapboxMarker | null>(null);
  const driverMarkerRef = useRef<MapboxMarker | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const latestDriverRef = useRef<LatLng | null>(driverLocation);

  useEffect(() => {
    latestDriverRef.current = driverLocation;
  }, [driverLocation]);

  useEffect(() => {
    let isMounted = true;
    let eventSource: EventSource | null = null;

    const updateLineAndBounds = (driver: LatLng) => {
      const map = mapRef.current;
      if (!map) return;

      const source = map.getSource(DRIVER_SOURCE_ID);
      source?.setData({
        type: "Feature",
        geometry: {
          type: "LineString",
          coordinates: [
            [driver.lng, driver.lat],
            [customerLocation.lng, customerLocation.lat],
          ],
        },
        properties: {},
      });

      map.fitBounds(
        [
          [Math.min(driver.lng, customerLocation.lng), Math.min(driver.lat, customerLocation.lat)],
          [Math.max(driver.lng, customerLocation.lng), Math.max(driver.lat, customerLocation.lat)],
        ],
        { padding: 90, duration: 600 },
      );
    };

    const animateDriverTo = (target: LatLng) => {
      const marker = driverMarkerRef.current;
      if (!marker) return;

      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }

      const start = marker.getLngLat();
      const startTime = performance.now();
      const duration = 900;

      const step = (now: number) => {
        const progress = Math.min(1, (now - startTime) / duration);
        const eased = 1 - Math.pow(1 - progress, 3);

        const next = {
          lng: start.lng + (target.lng - start.lng) * eased,
          lat: start.lat + (target.lat - start.lat) * eased,
        };

        marker.setLngLat([next.lng, next.lat]);
        updateLineAndBounds({ lat: next.lat, lng: next.lng });

        if (progress < 1) {
          animationFrameRef.current = requestAnimationFrame(step);
        }
      };

      animationFrameRef.current = requestAnimationFrame(step);
    };

    const upsertDriverMarker = (position: LatLng) => {
      const map = mapRef.current;
      if (!map) return;

      if (!driverMarkerRef.current) {
        driverMarkerRef.current = new mapboxgl.Marker({
          element: createMarkerElement("h-5 w-5 rounded-full border-2 border-white bg-amber-500 shadow-md"),
        })
          .setLngLat([position.lng, position.lat])
          .addTo(map);

        updateLineAndBounds(position);
        return;
      }

      animateDriverTo(position);
    };

    const initMap = async () => {
      if (!containerRef.current) return;

      console.info("mapboxgl loaded:", typeof mapboxgl);

      try {
        const map = await createMapInstance({
          container: "tracking-map",
          center: [customerLocation.lng, customerLocation.lat],
          zoom: 14,
          pitch: 0,
          bearing: 0,
          style: "mapbox://styles/mapbox/streets-v12",
        });

        if (!isMounted) {
          map.remove();
          return;
        }

        mapRef.current = map;

        customerMarkerRef.current = new mapboxgl.Marker({
          element: createMarkerElement("h-5 w-5 rounded-full border-2 border-white bg-emerald-500 shadow-md"),
        })
          .setLngLat([customerLocation.lng, customerLocation.lat])
          .addTo(map);

        map.on("load", () => {
          if (!map.getSource(DRIVER_SOURCE_ID)) {
            map.addSource(DRIVER_SOURCE_ID, {
              type: "geojson",
              data: {
                type: "Feature",
                geometry: {
                  type: "LineString",
                  coordinates: [],
                },
                properties: {},
              },
            });
          }

          if (!map.getLayer(DRIVER_LAYER_ID)) {
            map.addLayer({
              id: DRIVER_LAYER_ID,
              type: "line",
              source: DRIVER_SOURCE_ID,
              paint: {
                "line-color": "#f59e0b",
                "line-width": 4,
                "line-opacity": 0.85,
              },
            });
          }

          if (latestDriverRef.current) {
            upsertDriverMarker(latestDriverRef.current);
          }
        });

        eventSource = new EventSource(`/sse/delivery/${orderId}`, { withCredentials: true });
        eventSource.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data) as unknown;
            const nextPosition = parseIncomingDriverPosition(payload);

            if (!nextPosition) return;

            latestDriverRef.current = nextPosition;
            upsertDriverMarker(nextPosition);
          } catch {
            // ignore malformed payloads
          }
        };
      } catch (error) {
        console.error("Map initialization failed", error);
      }
    };

    void initMap();

    return () => {
      isMounted = false;
      eventSource?.close();
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      customerMarkerRef.current?.remove();
      driverMarkerRef.current?.remove();
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [customerLocation.lat, customerLocation.lng, orderId]);

  return <div ref={containerRef} id="tracking-map" className="h-[420px] w-full overflow-hidden rounded-2xl" />;
}
