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

declare global {
  interface Window {
    google?: {
      maps?: GoogleMapsNamespace;
    };
  }
}

export default function CustomerTrackingMap(_props: CustomerTrackingMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const googleMaps = (window as { google?: { maps?: GoogleMapsNamespace } }).google?.maps;

    console.log("google:", (window as { google?: unknown }).google);
    console.log("container:", containerRef.current);

    if (!googleMaps) {
    console.log("google:", window.google);
    console.log("container:", containerRef.current);

    if (!window.google || !window.google.maps) {
      console.error("Google Maps not loaded");
      return;
    }

    const map = new googleMaps.Map(containerRef.current, {
    const map = new window.google.maps.Map(containerRef.current, {
      center: { lat: -23.5505, lng: -46.6333 },
      zoom: 12,
    });

    setTimeout(() => {
      googleMaps.event.trigger(map, "resize");
      window.google?.maps?.event.trigger(map, "resize");
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
