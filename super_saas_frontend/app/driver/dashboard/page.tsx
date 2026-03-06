"use client";

import { useState } from "react";
import DriverLayout from "@/components/DriverLayout";
import { useDriverStatus } from "@/hooks/useDriverStatus";

export default function DriverDashboardPage() {
  const { online, isHydrated, setOnline, setOffline } = useDriverStatus();
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  async function handleOnline() {
    setStatusMessage(null);

    try {
      await setOnline();
    } catch (err) {
      console.error("Driver status error", err);
      setStatusMessage("Não foi possível atualizar o status. Tente novamente.");
    }
  }

  async function handleOffline() {
    setStatusMessage(null);

    try {
      await setOffline();
    } catch (err) {
      console.error("Driver status error", err);
      setStatusMessage("Não foi possível atualizar o status. Tente novamente.");
    }
  }

  return (
    <DriverLayout title="Dashboard do Entregador">
      <div className="space-y-4 rounded-lg border bg-white p-4">
        <p className="text-sm">
          Status atual: <strong>{isHydrated && online ? "Online" : "Offline"}</strong>
        </p>
        {statusMessage ? <p className="text-xs text-rose-600">{statusMessage}</p> : null}
        <div className="grid grid-cols-2 gap-3">
          <button className="rounded bg-emerald-600 py-2 text-white" onClick={handleOnline}>
            Ficar online
          </button>
          <button className="rounded bg-slate-700 py-2 text-white" onClick={handleOffline}>
            Ficar offline
          </button>
        </div>
      </div>
    </DriverLayout>
  );
}
