"use client";

import { useEffect } from "react";

const isLegacyDriverCache = (name: string) =>
  ["driver-shell", "driver-api", "driver-images", "driver-assets", "driver-precache"].includes(name) ||
  (name.startsWith("service-delivery-") && name.includes("service-delivery-driver-"));

export default function RetireDriverPwa() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    void navigator.serviceWorker.getRegistrations().then(async (registrations) => {
      await Promise.all(registrations
        .filter((registration) => {
          const path = new URL(registration.scope).pathname;
          return path === "/driver" || path === "/driver/";
        })
        .map((registration) => registration.unregister()));

      if ("caches" in window) {
        const names = await caches.keys();
        await Promise.all(names.filter(isLegacyDriverCache).map((name) => caches.delete(name)));
      }
    }).catch(() => undefined);
  }, []);

  return null;
}
