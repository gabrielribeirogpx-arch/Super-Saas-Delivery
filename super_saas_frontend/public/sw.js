// Retire the legacy driver PWA. The Android app is distributed through /baixar-entregador.
const isLegacyDriverCache = (name) =>
  ["driver-shell", "driver-api", "driver-images", "driver-assets", "driver-precache"].includes(name) ||
  (name.startsWith("service-delivery-") && name.includes("service-delivery-driver-"));

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter(isLegacyDriverCache).map((name) => caches.delete(name)));
    await self.registration.unregister();
  })());
});
