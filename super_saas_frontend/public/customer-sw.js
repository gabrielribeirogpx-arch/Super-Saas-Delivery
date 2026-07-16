const VERSION = "customer-pwa-v2-20260716";
const HOST_CACHE_PREFIX = `service-delivery-customer:${self.location.hostname}:${VERSION}`;
const SHELL_CACHE = `${HOST_CACHE_PREFIX}:shell`;
const MENU_CACHE = `${HOST_CACHE_PREFIX}:menu`;
const IMAGE_CACHE = `${HOST_CACHE_PREFIX}:images`;
const ASSET_CACHE = `${HOST_CACHE_PREFIX}:assets`;
const OFFLINE_HTML = `<!doctype html><html lang="pt-BR"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Offline</title><body style="font-family:system-ui;padding:24px"><h1>Você está offline</h1><p>O cardápio já visitado pode continuar disponível. Conecte-se para finalizar pedidos e acompanhar entregas.</p></body></html>`;

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});
self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(SHELL_CACHE).then((cache) => cache.addAll(["/"]).catch(() => undefined)));
});
self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith(`service-delivery-customer:${self.location.hostname}:`) && !key.startsWith(HOST_CACHE_PREFIX)).map((key) => caches.delete(key)))));
  self.clients.claim();
});

const isSensitiveApi = (url) => url.pathname.includes("/orders") || url.pathname.includes("/checkout") || url.pathname.includes("/track") || url.pathname.includes("/tracking") || url.pathname.includes("/sse") || url.pathname.startsWith("/api/admin") || url.pathname.startsWith("/ws");
async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok && request.method === "GET") cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    if (request.mode === "navigate") return new Response(OFFLINE_HTML, { headers: { "Content-Type": "text/html; charset=utf-8" } });
    throw error;
  }
}
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const network = fetch(request).then((response) => { if (response.ok) cache.put(request, response.clone()); return response; }).catch(() => cached);
  return cached || network;
}
async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || request.method !== "GET") return;
  if (isSensitiveApi(url)) { event.respondWith(fetch(request)); return; }
  if (url.pathname === "/api/public/pwa/manifest" || url.pathname.startsWith("/api/public/pwa/icon/")) { event.respondWith(networkFirst(request, ASSET_CACHE)); return; }
  if (url.pathname.includes("/public/menu") || url.pathname.includes("/api/public/") && url.pathname.endsWith("/menu")) { event.respondWith(networkFirst(request, MENU_CACHE)); return; }
  if (request.destination === "image") { event.respondWith(cacheFirst(request, IMAGE_CACHE)); return; }
  if (request.mode === "navigate") { event.respondWith(networkFirst(request, SHELL_CACHE)); return; }
  if (["script", "style", "font"].includes(request.destination) || url.pathname.startsWith("/_next/static/")) { event.respondWith(staleWhileRevalidate(request, SHELL_CACHE)); }
});
