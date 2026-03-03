"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api, baseUrl } from "@/lib/api";
import { authApi } from "@/lib/auth";

interface DeliveryUser {
  id: number;
  name: string;
  role: string;
}

interface DeliveryUserLocation {
  delivery_user_id: number;
  lat: number;
  lng: number;
  updated_at: string;
}

type DeliveryPresence = "online" | "offline";

interface MarkerState {
  marker: LeafletMarker;
  status: DeliveryPresence;
  name: string;
  updatedAt: string;
  animationFrame?: number;
}

interface LeafletMap {
  remove: () => void;
  fitBounds: (bounds: unknown, options?: Record<string, unknown>) => void;
  setView: (latLng: [number, number], zoom: number) => void;
}

interface LeafletMarker {
  setLatLng: (latLng: [number, number]) => LeafletMarker;
  getLatLng: () => { lat: number; lng: number };
  addTo: (map: LeafletMap) => LeafletMarker;
  bindPopup: (content: string) => LeafletMarker;
  setPopupContent: (content: string) => LeafletMarker;
  setIcon: (icon: unknown) => LeafletMarker;
}

interface LeafletGlobal {
  map: (container: HTMLElement) => LeafletMap;
  tileLayer: (url: string, options: Record<string, unknown>) => { addTo: (map: LeafletMap) => void };
  marker: (latLng: [number, number], options?: Record<string, unknown>) => LeafletMarker;
  divIcon: (options: Record<string, unknown>) => unknown;
  latLngBounds: (points: [number, number][]) => unknown;
}

declare global {
  interface Window {
    L?: LeafletGlobal;
  }
}

const LEAFLET_CSS_ID = "leaflet-cdn-css";
const LEAFLET_SCRIPT_ID = "leaflet-cdn-js";
const ANIMATION_DURATION_MS = 500;

function ensureLeafletAssets(): Promise<LeafletGlobal> {
  return new Promise((resolve, reject) => {
    if (window.L) {
      resolve(window.L);
      return;
    }

    if (!document.getElementById(LEAFLET_CSS_ID)) {
      const css = document.createElement("link");
      css.id = LEAFLET_CSS_ID;
      css.rel = "stylesheet";
      css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
      css.integrity = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=";
      css.crossOrigin = "";
      document.head.appendChild(css);
    }

    const existingScript = document.getElementById(LEAFLET_SCRIPT_ID) as HTMLScriptElement | null;
    if (existingScript) {
      existingScript.addEventListener("load", () => {
        if (window.L) {
          resolve(window.L);
          return;
        }
        reject(new Error("Leaflet indisponível após carregar script."));
      });
      existingScript.addEventListener("error", () => reject(new Error("Falha ao carregar Leaflet.")));
      return;
    }

    const script = document.createElement("script");
    script.id = LEAFLET_SCRIPT_ID;
    script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.integrity = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=";
    script.crossOrigin = "";
    script.async = true;
    script.onload = () => {
      if (window.L) {
        resolve(window.L);
        return;
      }
      reject(new Error("Leaflet indisponível após carregar script."));
    };
    script.onerror = () => reject(new Error("Falha ao carregar Leaflet."));
    document.body.appendChild(script);
  });
}

function toDisplayTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Data inválida";
  }

  return date.toLocaleString("pt-BR");
}

function markerIcon(L: LeafletGlobal, status: DeliveryPresence) {
  const color = status === "online" ? "#16a34a" : "#6b7280";

  return L.divIcon({
    className: "delivery-user-marker",
    html: `<span style="display:block;width:16px;height:16px;border-radius:50%;background:${color};border:2px solid #ffffff;box-shadow:0 0 0 2px rgba(15,23,42,0.25);"></span>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    popupAnchor: [0, -8],
  });
}

function popupContent(name: string, status: DeliveryPresence, updatedAt: string) {
  const statusLabel = status === "online" ? "Online" : "Offline";

  return `
    <div style="min-width:180px;line-height:1.4;">
      <strong>${name}</strong><br />
      Status: ${statusLabel}<br />
      Última atualização: ${toDisplayTimestamp(updatedAt)}
    </div>
  `;
}

function buildAdminWsUrl(pathname: string): string {
  const normalizedPath = pathname.startsWith("/") ? pathname : `/${pathname}`;

  if (baseUrl) {
    const withoutApiSuffix = baseUrl.endsWith("/api") ? baseUrl.slice(0, -4) : baseUrl;
    const wsBase = new URL(withoutApiSuffix);
    wsBase.protocol = wsBase.protocol === "https:" ? "wss:" : "ws:";
    wsBase.pathname = normalizedPath;
    wsBase.search = "";
    return wsBase.toString();
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${normalizedPath}`;
}

export default function AdminDeliveryMapPage() {
  const params = useParams<{ tenant_id: string }>();
  const tenantId = useMemo(() => {
    const parsed = Number(params.tenant_id);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [params.tenant_id]);

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markersRef = useRef<Map<number, MarkerState>>(new Map());

  const [mapError, setMapError] = useState<string | null>(null);

  const { data: currentUser, isLoading: meLoading } = useQuery({
    queryKey: ["admin-auth-me"],
    queryFn: () => authApi.me(),
  });

  const tenantMismatch =
    tenantId !== null &&
    currentUser?.tenant_id !== undefined &&
    Number(currentUser.tenant_id) !== Number(tenantId);

  const { data: deliveryUsers, isLoading: usersLoading } = useQuery({
    queryKey: ["delivery-users-map", tenantId],
    enabled: tenantId !== null && !tenantMismatch,
    queryFn: async () => {
      const users = await api.get<DeliveryUser[]>(`/api/admin/users?tenant_id=${tenantId}`);
      return users.filter((user) => user.role?.toUpperCase() === "DELIVERY");
    },
  });

  const { data: locations, isLoading: locationsLoading, isError, error } = useQuery({
    queryKey: ["delivery-users-locations", tenantId],
    enabled: tenantId !== null && !tenantMismatch,
    queryFn: () => api.get<DeliveryUserLocation[]>(`/api/admin/${tenantId}/delivery-users/locations`),
  });

  useEffect(() => {
    let mounted = true;

    ensureLeafletAssets()
      .then((L) => {
        if (!mounted || !mapContainerRef.current || mapRef.current) {
          return;
        }

        const map = L.map(mapContainerRef.current);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          maxZoom: 19,
        }).addTo(map);

        map.setView([-14.235, -51.9253], 4);
        mapRef.current = map;
      })
      .catch((cause) => {
        if (mounted) {
          setMapError(cause instanceof Error ? cause.message : "Falha ao iniciar o mapa.");
        }
      });

    return () => {
      mounted = false;

      markersRef.current.forEach((state) => {
        if (state.animationFrame) {
          window.cancelAnimationFrame(state.animationFrame);
        }
      });
      markersRef.current.clear();

      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !window.L || !deliveryUsers || !locations) {
      return;
    }

    const L = window.L;
    const map = mapRef.current;
    const userNameById = new Map(deliveryUsers.map((user) => [user.id, user.name]));

    locations.forEach((location) => {
      if (!Number.isFinite(location.lat) || !Number.isFinite(location.lng)) {
        return;
      }

      const existing = markersRef.current.get(location.delivery_user_id);
      const name = userNameById.get(location.delivery_user_id) ?? `Entregador #${location.delivery_user_id}`;
      const status: DeliveryPresence = existing?.status ?? "offline";

      if (existing) {
        existing.marker.setLatLng([location.lat, location.lng]);
        existing.updatedAt = location.updated_at;
        existing.name = name;
        existing.marker.setIcon(markerIcon(L, status));
        existing.marker.setPopupContent(popupContent(name, status, location.updated_at));
        return;
      }

      const marker = L.marker([location.lat, location.lng], {
        icon: markerIcon(L, status),
      })
         .addTo(map)
        .bindPopup(popupContent(name, status, location.updated_at));

      markersRef.current.set(location.delivery_user_id, {
        marker,
        status,
        updatedAt: location.updated_at,
        name,
      });
    });

    const points = Array.from(markersRef.current.values()).map((state) => {
      const pos = state.marker.getLatLng();
      return [pos.lat, pos.lng] as [number, number];
    });

    if (points.length > 1) {
      map.fitBounds(L.latLngBounds(points), { padding: [40, 40] });
    } else if (points.length === 1) {
      map.setView(points[0], 14);
    }
  }, [deliveryUsers, locations]);

  useEffect(() => {
    if (!mapRef.current || !window.L || tenantId === null || tenantMismatch) {
      return;
    }

    const L = window.L;
    const userNameById = new Map((deliveryUsers ?? []).map((user) => [user.id, user.name]));
    const ws = new WebSocket(buildAdminWsUrl("/ws/admin/delivery-status"));

    const smoothMoveMarker = (state: MarkerState, lat: number, lng: number) => {
      if (state.animationFrame) {
        window.cancelAnimationFrame(state.animationFrame);
      }

      const start = state.marker.getLatLng();
      const startTime = performance.now();

      const tick = (now: number) => {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / ANIMATION_DURATION_MS, 1);
        const nextLat = start.lat + (lat - start.lat) * progress;
        const nextLng = start.lng + (lng - start.lng) * progress;
        state.marker.setLatLng([nextLat, nextLng]);

        if (progress < 1) {
          state.animationFrame = window.requestAnimationFrame(tick);
          return;
        }

        state.animationFrame = undefined;
      };

      state.animationFrame = window.requestAnimationFrame(tick);
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as {
          delivery_user_id?: number;
          lat?: number;
          lng?: number;
          status?: string;
          updated_at?: string;
        };

        const deliveryUserId = Number(payload.delivery_user_id);
        if (!Number.isFinite(deliveryUserId)) {
          return;
        }

        const current = markersRef.current.get(deliveryUserId);
        const name = userNameById.get(deliveryUserId) ?? current?.name ?? `Entregador #${deliveryUserId}`;
        const incomingStatus = payload.status?.toLowerCase() === "online" ? "online" : payload.status?.toLowerCase() === "offline" ? "offline" : current?.status ?? "offline";
        const timestamp = payload.updated_at ?? new Date().toISOString();

        if (Number.isFinite(payload.lat) && Number.isFinite(payload.lng)) {
          if (current) {
            smoothMoveMarker(current, Number(payload.lat), Number(payload.lng));
            current.status = incomingStatus;
            current.updatedAt = timestamp;
            current.name = name;
            current.marker.setIcon(markerIcon(L, current.status));
            current.marker.setPopupContent(popupContent(name, current.status, current.updatedAt));
          } else {
            const marker = L.marker([Number(payload.lat), Number(payload.lng)], {
              icon: markerIcon(L, incomingStatus),
            })
              .addTo(mapRef.current as LeafletMap)
              .bindPopup(popupContent(name, incomingStatus, timestamp));

            markersRef.current.set(deliveryUserId, {
              marker,
              status: incomingStatus,
              updatedAt: timestamp,
              name,
            });

            const points = Array.from(markersRef.current.values()).map((state) => {
              const pos = state.marker.getLatLng();
              return [pos.lat, pos.lng] as [number, number];
            });
            if (points.length > 1) {
              mapRef.current?.fitBounds(L.latLngBounds(points), { padding: [40, 40] });
            }
          }
          return;
        }

        if (payload.status && current) {
          current.status = incomingStatus;
          current.updatedAt = timestamp;
          current.name = name;
          current.marker.setIcon(markerIcon(L, current.status));
          current.marker.setPopupContent(popupContent(name, current.status, current.updatedAt));
        }
      } catch {
        // ignora payload inválido para manter resiliência do socket
      }
    };

    ws.onerror = () => {
      setMapError((currentError) => currentError ?? "Conexão em tempo real instável. Tente recarregar a página.");
    };

    return () => {
      ws.close();
    };
  }, [deliveryUsers, tenantId, tenantMismatch]);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Mapa de entregadores</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-sm text-slate-600">Tenant selecionado: {params.tenant_id}</p>
          {tenantId === null ? <p className="text-sm text-red-600">Tenant inválido.</p> : null}
          {tenantMismatch ? (
            <p className="text-sm text-red-600">Tenant não autorizado para o usuário autenticado.</p>
          ) : null}
          {mapError ? <p className="text-sm text-red-600">{mapError}</p> : null}
          {isError ? (
            <p className="text-sm text-red-600">
              {error instanceof ApiError ? error.message : "Erro ao carregar localizações de entregadores."}
            </p>
          ) : null}
          {meLoading || usersLoading || locationsLoading ? (
            <p className="text-sm text-slate-500">Carregando mapa de entregas...</p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div ref={mapContainerRef} className="h-[70vh] w-full rounded-lg border border-slate-200" />
        </CardContent>
      </Card>
    </div>
  );
}
