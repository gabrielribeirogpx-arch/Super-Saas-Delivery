"use client";

import { useState } from "react";
import DriverLayout from "@/components/DriverLayout";
import { setDriverOffline, setDriverOnline } from "@/services/delivery";

export default function DriverDashboardPage() {
  const [online, setOnline] = useState(false);

  async function handleOnline() {
    await setDriverOnline();
    setOnline(true);
  }

  async function handleOffline() {
    await setDriverOffline();
    setOnline(false);
  }

  return (
    <DriverLayout title="Dashboard do Entregador">
      <div className="space-y-4 rounded-lg border bg-white p-4">
        <p className="text-sm">
          Status atual: <strong>{online ? "Online" : "Offline"}</strong>
        </p>
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
