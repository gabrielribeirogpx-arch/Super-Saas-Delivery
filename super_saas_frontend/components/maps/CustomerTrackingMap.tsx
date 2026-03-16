"use client";

import { useEffect, useRef } from "react";

type LatLng = {
  lat: number;
  lng: number;
};

type CustomerTrackingMapProps = {
  orderId: string;
  apiKey: string;
  driverLocation: LatLng | null;
  customerLocation: LatLng;
};

export default function CustomerTrackingMap({ orderId, apiKey, driverLocation, customerLocation }: CustomerTrackingMapProps) {
  const mapRef = useRef<any>(null);
  const driverMarkerRef = useRef<any>(null);
  const directionsRendererRef = useRef<any>(null);
  const directionsServiceRef = useRef<any>(null);
  const latestDriverPositionRef = useRef<LatLng | null>(driverLocation);

  const hasValidDriverLocation =
    driverLocation !== null && Number.isFinite(driverLocation.lat) && Number.isFinite(driverLocation.lng);

  const hasApiKey = typeof apiKey === "string" && apiKey.trim().length > 0;

  useEffect(() => {
    latestDriverPositionRef.current = driverLocation;
  }, [driverLocation]);

  useEffect(() => {
    console.log("CustomerTrackingMap mounted");

    if (!hasApiKey) {
      console.error("Google Maps API key is missing. Map cannot initialize.");
      return;
    }

    let isMounted = true;
    let eventSource: EventSource | null = null;
    let routeInterval: ReturnType<typeof setInterval> | null = null;
    let scriptLoadHandler: (() => void) | null = null;
    let existingScript: HTMLScriptElement | null = null;

    const renderRoute = () => {
      const googleMaps = (window as Window & { google?: any }).google;
      const mapInstance = mapRef.current;
      const directionsService = directionsServiceRef.current;
      const directionsRenderer = directionsRendererRef.current;

      if (!googleMaps?.maps || !mapInstance || !directionsService || !directionsRenderer) {
        return;
      }

      if (!latestDriverPositionRef.current) {
        return;
      }

      directionsService.route(
        {
          origin: latestDriverPositionRef.current,
          destination: customerLocation,
          travelMode: googleMaps.maps.TravelMode.DRIVING,
        },
        (response: any, status: string) => {
          if (status === "OK" && response) {
            directionsRenderer.setDirections(response);
          }
        },
      );
    };

    const initMap = () => {
      const googleMaps = (window as Window & { google?: any }).google;
      const mapElement = document.getElementById("tracking-map");

      if (!isMounted || !googleMaps?.maps || !mapElement) {
        return;
      }

      if (!mapRef.current) {
        const map = new googleMaps.maps.Map(mapElement, {
          center: customerLocation,
          zoom: 15,
          disableDefaultUI: true,
        });
        mapRef.current = map;

        directionsServiceRef.current = new googleMaps.maps.DirectionsService();
        directionsRendererRef.current = new googleMaps.maps.DirectionsRenderer({
          map,
          suppressMarkers: true,
          preserveViewport: true,
        });

        if (hasValidDriverLocation) {
          driverMarkerRef.current = new googleMaps.maps.Marker({
            map,
            position: driverLocation,
            icon: "/icons/motorcycle.png",
          });
        }

        console.log("Google Map initialized");
      } else {
        return;
      }

      if (latestDriverPositionRef.current) {
        renderRoute();
      }

      eventSource = new EventSource(`/events/delivery/${orderId}`);
      console.log("Delivery SSE connected for order", orderId);
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as { lat?: number; lng?: number };
          const nextPosition = {
            lat: Number(data.lat),
            lng: Number(data.lng),
          };

          if (!Number.isFinite(nextPosition.lat) || !Number.isFinite(nextPosition.lng)) {
            return;
          }

          latestDriverPositionRef.current = nextPosition;

          if (!driverMarkerRef.current && mapRef.current) {
            driverMarkerRef.current = new googleMaps.maps.Marker({
              map: mapRef.current,
              position: nextPosition,
              icon: "/icons/motorcycle.png",
            });
          }

          driverMarkerRef.current?.setPosition(nextPosition);
        } catch {
          // ignore malformed SSE payloads
        }
      };

      routeInterval = setInterval(() => {
        if (latestDriverPositionRef.current) {
          renderRoute();
        }
      }, 10000);
    };

    const boot = () => {
      const browserWindow = window as Window & { google?: any };

      if (browserWindow.google?.maps) {
        initMap();
        return;
      }

      existingScript = document.querySelector<HTMLScriptElement>('script[src*="maps.googleapis.com/maps/api/js"]');

      scriptLoadHandler = () => {
        console.log("Google Maps API loaded");
        initMap();
      };

      if (existingScript) {
        if (browserWindow.google?.maps) {
          initMap();
          return;
        }

        existingScript.addEventListener("load", scriptLoadHandler, { once: true });
        return;
      }

      const script = document.createElement("script");
      script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=geometry`;
      script.async = true;
      script.defer = true;
      script.onload = scriptLoadHandler;

      document.head.appendChild(script);
    };

    void boot();

    return () => {
      isMounted = false;
      if (routeInterval) {
        clearInterval(routeInterval);
      }
      if (existingScript && scriptLoadHandler) {
        existingScript.removeEventListener("load", scriptLoadHandler);
      }
      eventSource?.close();
    };
  }, [apiKey, customerLocation, hasApiKey, hasValidDriverLocation, driverLocation, orderId]);

  if (!hasApiKey) {
    return (
      <div id="tracking-map" className="h-[420px] w-full overflow-hidden rounded-2xl bg-slate-100 p-4 text-sm text-slate-600">
        Map unavailable – configuration error
      </div>
    );
  }

  return <div id="tracking-map" className="h-[420px] w-full overflow-hidden rounded-2xl" />;
}
