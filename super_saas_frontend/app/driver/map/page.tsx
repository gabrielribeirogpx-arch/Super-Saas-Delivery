"use client";

import { useMemo, useState } from "react";
import DriverLayout from "@/components/DriverLayout";
import DeliveryMap from "@/components/DeliveryMap";
import { useDriverLocation } from "@/hooks/useDriverLocation";

export default function DriverMapPage() {
  const { position, error } = useDriverLocation(true);
  const [drawRoute, setDrawRoute] = useState(false);

  const destination = useMemo(() => {
    if (typeof window === "undefined") {
      return null;
    }

    const raw = localStorage.getItem("driver_destination");
    if (!raw) {
      return null;
    }

    try {
      return JSON.parse(raw) as { lat: number; lng: number };
    } catch {
      return null;
    }
  }, []);

  return (
    <DriverLayout title="Mapa da entrega">
      <div className="space-y-3">
        <DeliveryMap driverPosition={position} destination={destination} drawRoute={drawRoute} />

        <button
          className="w-full rounded bg-blue-600 py-2 text-sm font-medium text-white"
          onClick={() => setDrawRoute(true)}
        >
          Iniciar entrega
        </button>

        {position ? (
          <p className="text-xs text-slate-600">
            Localização: {position.lat.toFixed(5)}, {position.lng.toFixed(5)}
          </p>
        ) : null}

        {error ? <p className="text-xs text-rose-600">Erro GPS: {error}</p> : null}
      </div>
    </DriverLayout>
  );
}
