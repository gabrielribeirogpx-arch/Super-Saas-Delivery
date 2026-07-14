/* global workbox */
importScripts("https://storage.googleapis.com/workbox-cdn/releases/7.1.0/workbox-sw.js");

const VERSION = "service-delivery-driver-v2";
const OFFLINE_URL = "/offline.html";
// TODO: Replace temporary icons with real PWA PNG assets (192/512/maskable)
const DRIVER_SHELL = ["/driver", "/driver/dashboard", "/driver/deliveries", OFFLINE_URL, "/manifest.webmanifest", "/icon.svg", "/service-delivery-logo.svg"];

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});

workbox.setConfig({ debug: false });
workbox.core.setCacheNameDetails({ prefix: "service-delivery", suffix: VERSION });
workbox.core.clientsClaim();
workbox.precaching.cleanupOutdatedCaches();

workbox.routing.registerRoute(
  ({ request, url }) => request.mode === "navigate" && url.pathname.startsWith("/driver"),
  new workbox.strategies.NetworkFirst({
    cacheName: "driver-shell",
    networkTimeoutSeconds: 4,
    plugins: [
      new workbox.expiration.ExpirationPlugin({ maxEntries: 24, maxAgeSeconds: 7 * 24 * 60 * 60 }),
      { handlerDidError: async () => (await caches.match("/driver")) || caches.match(OFFLINE_URL) },
    ],
  }),
);

workbox.routing.registerRoute(
  ({ url, request }) => url.pathname.startsWith("/api/") && request.method === "GET",
  new workbox.strategies.NetworkFirst({
    cacheName: "driver-api",
    networkTimeoutSeconds: 4,
    plugins: [new workbox.expiration.ExpirationPlugin({ maxEntries: 60, maxAgeSeconds: 24 * 60 * 60 })],
  }),
);

workbox.routing.registerRoute(
  ({ request }) => request.destination === "image",
  new workbox.strategies.CacheFirst({
    cacheName: "driver-images",
    plugins: [new workbox.expiration.ExpirationPlugin({ maxEntries: 120, maxAgeSeconds: 30 * 24 * 60 * 60 })],
  }),
);

workbox.routing.registerRoute(
  ({ request, url }) => ["style", "script", "font", "worker"].includes(request.destination) || url.pathname.startsWith("/_next/static/"),
  new workbox.strategies.StaleWhileRevalidate({
    cacheName: "driver-assets",
    plugins: [new workbox.expiration.ExpirationPlugin({ maxEntries: 160, maxAgeSeconds: 30 * 24 * 60 * 60 })],
  }),
);

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open("driver-precache").then((cache) => cache.addAll(DRIVER_SHELL)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith("service-delivery-") && !key.endsWith(VERSION)).map((key) => caches.delete(key)))),
  );
});
