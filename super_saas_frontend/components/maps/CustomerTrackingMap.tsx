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
  const customerMarkerRef = useRef<any>(null);
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
    console.info("Chave da API do Maps presente:", !!process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY);
    console.info("Google Maps apiKey prop presente:", hasApiKey);

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
        directionsRenderer.set("directions", null);
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

        customerMarkerRef.current = new googleMaps.maps.Marker({
          map,
          position: customerLocation,
          title: "Customer",
        });

        if (hasValidDriverLocation) {
          driverMarkerRef.current = new googleMaps.maps.Marker({
            map,
            position: driverLocation,
            icon: "/icons/motorcycle.png",
            title: "Driver",
          });
        }

        console.log("Google Map initialized");
      }

      mapRef.current?.setCenter(customerLocation);
      customerMarkerRef.current?.setPosition(customerLocation);
      renderRoute();

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
              title: "Driver",
            });
          }

          driverMarkerRef.current?.setPosition(nextPosition);
          renderRoute();
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

      existingScript = document.querySelector<HTMLScriptElement>(`script[src="https://maps.googleapis.com/maps/api/js?key=${apiKey}"]`);

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
        console.info("Google Maps script já estava presente no DOM", {
          scriptFound: true,
          src: existingScript.src,
        });
        return;
      }

      const script = document.createElement("script");
      script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}`;
      script.async = true;
      script.defer = true;
      script.onload = scriptLoadHandler;
      script.onerror = () => {
        console.error("Falha ao carregar script do Google Maps", {
          src: script.src,
        });
      };

      document.head.appendChild(script);
      const injectedScript = document.querySelector<HTMLScriptElement>(`script[src="${script.src}"]`);
      console.info("Script do Google Maps injetado no DOM:", !!injectedScript, injectedScript?.src);
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
      <div className="h-[420px] w-full overflow-hidden rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        Não foi possível carregar o mapa: a variável NEXT_PUBLIC_GOOGLE_MAPS_API_KEY não está configurada no build do Next.js.
      </div>
    );
  }

  return <div id="tracking-map" className="h-[420px] w-full overflow-hidden rounded-2xl" />;
}
