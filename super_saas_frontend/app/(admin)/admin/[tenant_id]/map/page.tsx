"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import type { LngLatTuple, MapboxGeoJSONSource, MapboxMap } from "@/lib/maps/types";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api, baseUrl } from "@/lib/api";
import { authApi } from "@/lib/auth";
import { createMapInstance } from "@/lib/maps/mapInstance";
import { DriverMarker } from "@/lib/maps/driverMarker";
import { ensureRouteLayer, fetchRoute } from "@/lib/maps/routeLayer";
import { listenOrderLocation, listenTenantDeliveryStatus } from "@/lib/maps/sseLocation";
import { TrackingAnimator } from "@/lib/maps/trackingAnimator";

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
  status?: string;
}

type PointFeature = GeoJSON.Feature<GeoJSON.Point, { id: number; name: string; status: string; updatedAt: string }>;

const DELIVERY_SOURCE_ID = "delivery-users";

function buildFeature(location: DeliveryUserLocation, name: string): PointFeature {
  return {
    type: "Feature",
    geometry: { type: "Point", coordinates: [location.lng, location.lat] },
    properties: {
      id: location.delivery_user_id,
      name,
      status: location.status ?? "OFFLINE",
      updatedAt: location.updated_at,
    },
  };
}

function headingFromPoints(from: LngLatTuple, to: LngLatTuple): number {
  const [fromLng, fromLat] = from;
  const [toLng, toLat] = to;
  const angle = (Math.atan2(toLng - fromLng, toLat - fromLat) * 180) / Math.PI;
  return (angle + 360) % 360;
}

function apiBaseUrl(): string {
  if (baseUrl) return baseUrl;
  if (typeof window !== "undefined") return window.location.origin;
  return "";
}

export default function AdminDeliveryMapPage() {
  const params = useParams<{ tenant_id: string }>();
  const searchParams = useSearchParams();
  const tenantId = useMemo(() => {
    const parsed = Number(params.tenant_id);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [params.tenant_id]);
  const trackedOrderId = useMemo(() => {
    const parsed = Number(searchParams.get("order_id"));
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);
  const destination = useMemo<[number, number] | null>(() => {
    const lat = Number(searchParams.get("destination_lat"));
    const lng = Number(searchParams.get("destination_lng"));
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      return null;
    }
    return [lng, lat];
  }, [searchParams]);

  const [mapError, setMapError] = useState<string | null>(null);
  const [followMode, setFollowMode] = useState(true);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapboxMap | null>(null);
  const driverMarkerRef = useRef<DriverMarker | null>(null);
  const animatorRef = useRef<TrackingAnimator | null>(null);
  const closeLocationStreamRef = useRef<(() => void) | null>(null);
  const closeStatusStreamRef = useRef<(() => void) | null>(null);
  const featuresRef = useRef<Map<number, PointFeature>>(new Map());

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
    if (!containerRef.current || mapRef.current) return;

    let active = true;

    createMapInstance({ container: containerRef.current })
      .then((map) => {
        if (!active) {
          map.remove();
          return;
        }

        mapRef.current = map;
        map.on("load", () => {
        map.addSource(DELIVERY_SOURCE_ID, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
          cluster: true,
          clusterRadius: 50,
          clusterMaxZoom: 14,
        });

        map.addLayer({
          id: "delivery-clusters",
          type: "circle",
          source: DELIVERY_SOURCE_ID,
          filter: ["has", "point_count"],
          paint: {
            "circle-color": "#1d4ed8",
            "circle-radius": ["step", ["get", "point_count"], 18, 20, 24, 50, 30],
          },
        });

        map.addLayer({
          id: "delivery-cluster-count",
          type: "symbol",
          source: DELIVERY_SOURCE_ID,
          filter: ["has", "point_count"],
          layout: { "text-field": ["get", "point_count_abbreviated"], "text-size": 12 },
          paint: { "text-color": "#ffffff" },
        });

        map.addLayer({
          id: "delivery-unclustered",
          type: "circle",
          source: DELIVERY_SOURCE_ID,
          filter: ["!", ["has", "point_count"]],
          paint: {
            "circle-radius": 8,
            "circle-color": [
              "match",
              ["upcase", ["coalesce", ["get", "status"], "OFFLINE"]],
              "ONLINE",
              "#16a34a",
              "BUSY",
              "#f59e0b",
              "#6b7280",
            ],
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          },
        });

          ensureRouteLayer(map);
        });
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setMapError(cause instanceof Error ? cause.message : "Falha ao iniciar mapa.");
      });

    return () => {
      active = false;
      closeLocationStreamRef.current?.();
      closeStatusStreamRef.current?.();
      animatorRef.current?.cancel();
      driverMarkerRef.current?.remove();
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !deliveryUsers || !locations) return;

    const nameById = new Map(deliveryUsers.map((user) => [user.id, user.name]));
    featuresRef.current.clear();

    locations.forEach((location) => {
      if (!Number.isFinite(location.lat) || !Number.isFinite(location.lng)) return;
      const name = nameById.get(location.delivery_user_id) ?? `Entregador #${location.delivery_user_id}`;
      featuresRef.current.set(location.delivery_user_id, buildFeature(location, name));
    });

    const source = mapRef.current.getSource(DELIVERY_SOURCE_ID) as MapboxGeoJSONSource | undefined;
    source?.setData({ type: "FeatureCollection", features: Array.from(featuresRef.current.values()) });
  }, [deliveryUsers, locations]);


  useEffect(() => {
    if (!mapRef.current || tenantId === null || tenantMismatch) return;

    const apiBase = apiBaseUrl();
    if (!apiBase) return;

    closeStatusStreamRef.current?.();
    closeStatusStreamRef.current = listenTenantDeliveryStatus({
      apiBase,
      tenantId,
      onStatus: (payload) => {
        const deliveryUserId = Number(payload.delivery_user_id);
        if (!Number.isFinite(deliveryUserId)) return;

        const current = featuresRef.current.get(deliveryUserId);
        if (!current) return;

        const nextLng = Number.isFinite(Number(payload.lng)) ? Number(payload.lng) : current.geometry.coordinates[0];
        const nextLat = Number.isFinite(Number(payload.lat)) ? Number(payload.lat) : current.geometry.coordinates[1];

        current.geometry.coordinates = [nextLng, nextLat];
        current.properties.status = payload.status ?? current.properties.status;
        current.properties.updatedAt = payload.updated_at ?? current.properties.updatedAt;

        const source = mapRef.current?.getSource(DELIVERY_SOURCE_ID) as MapboxGeoJSONSource | undefined;
        source?.setData({ type: "FeatureCollection", features: Array.from(featuresRef.current.values()) });
      },
    });

    return () => {
      closeStatusStreamRef.current?.();
      closeStatusStreamRef.current = null;
    };
  }, [tenantId, tenantMismatch]);

  useEffect(() => {
    if (!mapRef.current || trackedOrderId === null || tenantMismatch) return;

    const apiBase = apiBaseUrl();
    if (!apiBase) return;

    closeLocationStreamRef.current?.();

    closeLocationStreamRef.current = listenOrderLocation({
      apiBase,
      orderId: trackedOrderId,
      onLocation: async (payload) => {
        const map = mapRef.current;
        if (!map) return;

        const next: [number, number] = [payload.lng, payload.lat];
        if (!driverMarkerRef.current) {
          const marker = new DriverMarker(map, next, payload.status ?? "ONLINE");
          marker.setHeading(payload.heading ?? 0);
          driverMarkerRef.current = marker;
          animatorRef.current = new TrackingAnimator(marker);
          if (followMode) {
            map.easeTo({ center: next, zoom: 15, duration: 500 });
          }
          if (destination) {
            await fetchRoute(map, next, destination);
          }
          return;
        }

        const marker = driverMarkerRef.current;
        const animator = animatorRef.current;
        if (!marker || !animator) return;

        const previous = marker.getPosition();
        animator.animate([previous.lng, previous.lat], next);
        marker.setStatus(payload.status ?? "ONLINE");
        marker.setHeading(payload.heading ?? headingFromPoints([previous.lng, previous.lat], next));

        if (followMode) {
          map.easeTo({ center: next, duration: 500 });
        }

        if (destination) {
          await fetchRoute(map, next, destination);
        }
      },
    });

    return () => {
      closeLocationStreamRef.current?.();
      closeLocationStreamRef.current = null;
    };
  }, [destination, followMode, tenantMismatch, trackedOrderId]);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-3">
            <span>Mapa Enterprise de entregas</span>
            <button
              type="button"
              className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700"
              onClick={() => setFollowMode((prev) => !prev)}
            >
              Follow mode: {followMode ? "ON" : "OFF"}
            </button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-sm text-slate-600">Tenant selecionado: {params.tenant_id}</p>
          {trackedOrderId ? <p className="text-sm text-slate-600">Tracking pedido: #{trackedOrderId}</p> : null}
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
          <div ref={containerRef} className="h-[70vh] w-full rounded-lg border border-slate-200" />
        </CardContent>
      </Card>
    </div>
  );
}
