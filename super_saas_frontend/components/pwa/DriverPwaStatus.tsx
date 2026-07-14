"use client";

import { useEffect, useState } from "react";
import { flushPendingDriverActions, getPendingDriverActionCount } from "@/lib/driverOfflineQueue";
import { driverLocationService } from "@/services/driverLocationService";

export default function DriverPwaStatus() {
  const [offline, setOffline] = useState(false);
  const [pending, setPending] = useState(0);

  useEffect(() => {
    const sync = () => {
      setOffline(!navigator.onLine);
      setPending(getPendingDriverActionCount());
    };
    const online = () => {
      sync();
      void flushPendingDriverActions().finally(sync);
      void driverLocationService.retryLatest().catch(() => undefined);
    };

    sync();
    window.addEventListener("online", online);
    window.addEventListener("offline", sync);
    window.addEventListener("driver:pending-actions", sync as EventListener);
    if (navigator.onLine) void flushPendingDriverActions().finally(sync);

    return () => {
      window.removeEventListener("online", online);
      window.removeEventListener("offline", sync);
      window.removeEventListener("driver:pending-actions", sync as EventListener);
    };
  }, []);

  if (!offline && pending === 0) return null;

  return (
    <div className="fixed left-1/2 top-[max(0.75rem,env(safe-area-inset-top))] z-[9998] -translate-x-1/2 rounded-full border border-amber-200 bg-amber-50 px-4 py-2 text-xs font-semibold text-amber-900 shadow-lg" role="status" aria-live="polite">
      {offline ? "Offline" : "Online"}{pending > 0 ? ` · ${pending} ação(ões) pendente(s)` : ""}
    </div>
  );
}
