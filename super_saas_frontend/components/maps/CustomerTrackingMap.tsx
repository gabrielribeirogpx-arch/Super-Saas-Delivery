"use client";

import { useEffect, useRef } from "react";

type LatLng = {
  lat: number;
  lng: number;
};

type CustomerTrackingMapProps = {
  orderId: string;
  apiKey: string;
  driverLocation: LatLng;
  customerLocation: LatLng;
};

export default function CustomerTrackingMap({ orderId, apiKey, driverLocation, customerLocation }: CustomerTrackingMapProps) {
  const mapRef = useRef<any>(null);
  const driverMarkerRef = useRef<any>(null);
  const directionsRendererRef = useRef<any>(null);
  const directionsServiceRef = useRef<any>(null);
  const latestDriverPositionRef = useRef<LatLng>(driverLocation);

  useEffect(() => {
    latestDriverPositionRef.current = driverLocation;
  }, [driverLocation]);

  useEffect(() => {
    let isMounted = true;
    let eventSource: EventSource | null = null;
    let routeInterval: ReturnType<typeof setInterval> | null = null;

    const renderRoute = () => {
      const googleMaps = (window as Window & { google?: any }).google;
      const mapInstance = mapRef.current;
      const directionsService = directionsServiceRef.current;
      const directionsRenderer = directionsRendererRef.current;

      if (!googleMaps?.maps || !mapInstance || !directionsService || !directionsRenderer) {
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

        driverMarkerRef.current = new googleMaps.maps.Marker({
          map,
          position: driverLocation,
          icon: "/icons/motorcycle.png",
        });
      }

      renderRoute();

      eventSource = new EventSource(`/events/delivery/${orderId}`);
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
          driverMarkerRef.current?.setPosition(nextPosition);
        } catch {
          // ignore malformed SSE payloads
        }
      };

      routeInterval = setInterval(renderRoute, 10000);
    };

    const boot = () => {
      const browserWindow = window as Window & { google?: any };

      if (browserWindow.google?.maps) {
        initMap();
        return;
      }

      const existingScript = document.querySelector<HTMLScriptElement>('script[src*="maps.googleapis.com/maps/api/js"]');

      if (existingScript) {
        existingScript.addEventListener("load", initMap, { once: true });
        return;
      }

      const script = document.createElement("script");
      script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}`;
      script.async = true;
      script.onload = initMap;

      document.head.appendChild(script);
    };

    void boot();

    return () => {
      isMounted = false;
      if (routeInterval) {
        clearInterval(routeInterval);
      }
      eventSource?.close();
    };
  }, [apiKey, customerLocation, driverLocation, orderId]);

  return <div id="tracking-map" className="h-[420px] w-full overflow-hidden rounded-2xl" />;
}
