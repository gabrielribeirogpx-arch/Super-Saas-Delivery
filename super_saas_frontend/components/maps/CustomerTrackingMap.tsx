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

function loadGoogleMapsScript(apiKey: string) {
  return new Promise<GoogleMapsNamespace>((resolve, reject) => {
    const googleMaps = (window as { google?: { maps?: GoogleMapsNamespace } }).google?.maps;
    if (googleMaps) {
      resolve(googleMaps);
      return;
    }

    const existingScript = document.querySelector<HTMLScriptElement>('script[src*="maps.googleapis.com"]');

    if (existingScript) {
      existingScript.addEventListener("load", () => {
        const loadedMaps = (window as { google?: { maps?: GoogleMapsNamespace } }).google?.maps;
        if (loadedMaps) {
          resolve(loadedMaps);
          return;
        }

        reject(new Error("Google Maps script loaded without maps namespace."));
      });
      existingScript.addEventListener("error", () => {
        reject(new Error("Failed to load Google Maps script."));
      });
      return;
    }

    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}`;
    script.async = true;
    script.defer = true;

    script.onload = () => {
      const loadedMaps = (window as { google?: { maps?: GoogleMapsNamespace } }).google?.maps;
      if (loadedMaps) {
        resolve(loadedMaps);
        return;
      }

      reject(new Error("Google Maps script loaded without maps namespace."));
    };

    script.onerror = () => {
      reject(new Error("Failed to load Google Maps script."));
    };

    document.head.appendChild(script);
  });
}

export default function CustomerTrackingMap({ customerLocation }: CustomerTrackingMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
    if (!apiKey) {
      console.error("Missing NEXT_PUBLIC_GOOGLE_MAPS_API_KEY");
      return;
    }

    console.log("Google loaded:", !!(window as { google?: unknown }).google);
    console.log("Container height:", containerRef.current.offsetHeight);

    let map: GoogleMapInstance | undefined;

    loadGoogleMapsScript(apiKey)
      .then((maps) => {
        if (!containerRef.current) return;

        map = new maps.Map(containerRef.current, {
          center: customerLocation,
          zoom: 12,
        });

        setTimeout(() => {
          if (!map) return;
          maps.event.trigger(map, "resize");
        }, 300);
      })
      .catch((error) => {
        console.error("Map initialization failed", error);
      });
  }, [customerLocation]);

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
