"use client";

import { useEffect, useRef, useState } from "react";
import { sendDriverLocation } from "@/services/delivery";

type DriverPosition = {
  lat: number;
  lng: number;
};

const MAX_SEND_INTERVAL_MS = 5000;

export function useDriverLocation(enabled = true) {
  const [position, setPosition] = useState<DriverPosition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lastSentAtRef = useRef(0);

  useEffect(() => {
    if (!enabled || typeof navigator === "undefined" || !navigator.geolocation) {
      return;
    }

    const watchId = navigator.geolocation.watchPosition(
      async (pos) => {
        const current = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        };

        setPosition(current);

        const now = Date.now();
        if (now - lastSentAtRef.current < MAX_SEND_INTERVAL_MS) {
          return;
        }

        lastSentAtRef.current = now;

        try {
          await sendDriverLocation(current.lat, current.lng);
        } catch {
          // Mantém o app resiliente se o envio falhar momentaneamente.
        }
      },
      (geoError) => setError(geoError.message),
      {
        enableHighAccuracy: true,
        maximumAge: 3000,
      }
    );

    return () => navigator.geolocation.clearWatch(watchId);
  }, [enabled]);

  return { position, error };
}
