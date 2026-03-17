"use client";

import { useEffect, useRef } from "react";

type LatLng = {
  lat: number;
  lng: number;
};

type CustomerTrackingMapProps = {
  orderId: string;
  driverLocation: LatLng | null;
  customerLocation: LatLng;
};

type GoogleMapsNamespace = {
  Map: new (container: HTMLElement, options: { center: LatLng; zoom: number }) => GoogleMapInstance;
  event: {
    trigger: (instance: GoogleMapInstance, eventName: string) => void;
  };
};

type GoogleMapInstance = Record<string, unknown>;

export default function CustomerTrackingMap(_props: CustomerTrackingMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const googleMaps = (window as { google?: { maps?: GoogleMapsNamespace } }).google?.maps;

    console.log("google:", (window as { google?: unknown }).google);
    console.log("container:", containerRef.current);

    if (!googleMaps) {
      console.error("Google Maps not loaded");
      return;
    }

    const map = new googleMaps.Map(containerRef.current, {
      center: { lat: -23.5505, lng: -46.6333 },
      zoom: 12,
    });

    setTimeout(() => {
      googleMaps.event.trigger(map, "resize");
    }, 300);
  }, []);

  return (
    <div
      ref={containerRef}
      id="tracking-map"
      style={{
        width: "100%",
        height: "400px",
        minHeight: "300px",
      }}
      className="overflow-hidden rounded-2xl"
    />
  );
}
