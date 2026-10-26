"use client";

import { useEffect, useState } from "react";

export default function RegisterServiceWorker() {
  const [waitingWorker, setWaitingWorker] = useState<ServiceWorker | null>(null);

  useEffect(() => {
    if (!("serviceWorker" in navigator)) {
      console.info("[PWA] Service workers are not supported in this browser.");
      return;
    }

    let refreshing = false;
    const onControllerChange = () => {
      if (refreshing) return;
      refreshing = true;
      window.location.reload();
    };

    navigator.serviceWorker.addEventListener("controllerchange", onControllerChange);

    navigator.serviceWorker
      .register("/sw.js", { scope: "/driver" })
      .then((registration) => {
        console.info("[PWA] Service worker registered.", { scope: registration.scope });
        registration.addEventListener("updatefound", () => {
          const nextWorker = registration.installing;
          if (!nextWorker) return;
          nextWorker.addEventListener("statechange", () => {
            if (nextWorker.state === "installed" && navigator.serviceWorker.controller) {
              setWaitingWorker(nextWorker);
            }
          });
        });
      })
      .catch((error) => {
        console.error("[PWA] Service worker registration failed.", error);
      });

    return () => navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange);
  }, []);

  if (!waitingWorker) return null;

  return (
    <div className="fixed bottom-4 left-1/2 z-[9999] flex w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 items-center justify-between gap-3 rounded-2xl bg-slate-950 px-4 py-3 text-sm text-white shadow-2xl" role="status" aria-live="polite">
      <span>Nova versão disponível</span>
      <button
        type="button"
        className="rounded-xl bg-emerald-500 px-3 py-2 font-semibold text-slate-950"
        onClick={() => waitingWorker.postMessage({ type: "SKIP_WAITING" })}
      >
        Atualizar
      </button>
    </div>
  );
}
