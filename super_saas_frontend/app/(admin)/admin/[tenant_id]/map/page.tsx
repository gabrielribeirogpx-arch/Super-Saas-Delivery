"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import type { Feature, Point } from "geojson";
import type { LngLatTuple, MapboxGeoJSONSource, MapboxMap } from "@/lib/maps/types";

import { ApiError, api, baseUrl } from "@/lib/api";
import { authApi } from "@/lib/auth";
import { createMapInstance } from "@/lib/maps/mapInstance";
import { listenOrderLocation } from "@/lib/maps/sseLocation";
import { TrackingAnimator } from "@/lib/maps/trackingAnimator";

import { DriverMarker } from "./DriverMarker";
import { FloatingDriverCard } from "./FloatingDriverCard";
import { MapHeader } from "./MapHeader";
import { ensureRouteLayer, fetchRoute } from "./RouteLayer";

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

type PointFeature = Feature<Point, { id: number; name: string; status: string; updatedAt: string }>;

interface ActiveDriverInfo {
  name: string;
  status: string;
  updatedAt: string;
  eta?: string;
}

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
  const params = useParams<{ tenant_id?: string; restaurantId?: string }>();
  const searchParams = useSearchParams();
  const tenantId = useMemo(() => {
    const parsed = Number(params.tenant_id ?? params.restaurantId);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [params.restaurantId, params.tenant_id]);
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
  const [activeDriver, setActiveDriver] = useState<ActiveDriverInfo | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapboxMap | null>(null);
  const driverMarkerRef = useRef<DriverMarker | null>(null);
  const animatorRef = useRef<TrackingAnimator | null>(null);
  const closeLocationStreamRef = useRef<(() => void) | null>(null);
  const closeStatusStreamRef = useRef<(() => void) | null>(null);
  const featuresRef = useRef<Map<number, PointFeature>>(new Map());
  const driverAnimationFrameRef = useRef<Map<number, number>>(new Map());

  const { data: currentUser } = useQuery({
    queryKey: ["admin-auth-me"],
    queryFn: () => authApi.me(),
  });

  const tenantMismatch =
    tenantId !== null &&
    currentUser?.tenant_id !== undefined &&
    Number(currentUser.tenant_id) !== Number(tenantId);

  const { data: deliveryUsers } = useQuery({
    queryKey: ["delivery-users-map", tenantId],
    enabled: tenantId !== null && !tenantMismatch,
    queryFn: async () => {
      const users = await api.get<DeliveryUser[]>(`/api/admin/users?tenant_id=${tenantId}`);
      return users.filter((user) => user.role?.toUpperCase() === "DELIVERY");
    },
  });

  const { data: locations, isError, error } = useQuery({
    queryKey: ["delivery-users-locations", tenantId],
    enabled: tenantId !== null && !tenantMismatch,
    queryFn: () => api.get<DeliveryUserLocation[]>(`/api/admin/${tenantId}/delivery-users/locations`),
  });

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    let active = true;

    createMapInstance({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/navigation-night-v1",
      pitch: 48,
      bearing: -16,
      zoom: 5,
    })
      .then((map) => {
        if (!active) {
          map.remove();
          return;
        }

        mapRef.current = map;
        map.on("load", () => {
          map.setFog({
            color: "rgb(15,23,42)",
            "horizon-blend": 0.1,
            "high-color": "rgb(36, 92, 223)",
            "space-color": "rgb(0, 0, 0)",
            "star-intensity": 0.0,
          });

          if (!map.getLayer("3d-buildings")) {
            map.addLayer({
              id: "3d-buildings",
              source: "composite",
              "source-layer": "building",
              filter: ["==", "extrude", "true"],
              type: "fill-extrusion",
              minzoom: 14,
              paint: {
                "fill-extrusion-color": "#111827",
                "fill-extrusion-height": ["get", "height"],
                "fill-extrusion-base": ["get", "min_height"],
                "fill-extrusion-opacity": 0.6,
              },
            });
          }

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

    const knownDrivers = new Set((deliveryUsers ?? []).map((driver) => Number(driver.id)));
    const source = new EventSource("/api/delivery/live-map/stream", { withCredentials: true });

    const smoothMoveDriver = (driverId: number, from: LngLatTuple, to: LngLatTuple) => {
      const sourceRef = mapRef.current?.getSource(DELIVERY_SOURCE_ID) as MapboxGeoJSONSource | undefined;
      if (!sourceRef) return;

      const previousFrame = driverAnimationFrameRef.current.get(driverId);
      if (previousFrame) {
        cancelAnimationFrame(previousFrame);
      }

      const startAt = performance.now();
      const duration = 800;

      const tick = (now: number) => {
        const progress = Math.min(1, (now - startAt) / duration);
        const eased = progress * (2 - progress);
        const nextLng = from[0] + (to[0] - from[0]) * eased;
        const nextLat = from[1] + (to[1] - from[1]) * eased;

        const feature = featuresRef.current.get(driverId);
        if (!feature) return;

        feature.geometry.coordinates = [nextLng, nextLat];
        sourceRef.setData({ type: "FeatureCollection", features: Array.from(featuresRef.current.values()) });

        if (progress < 1) {
          const frameId = requestAnimationFrame(tick);
          driverAnimationFrameRef.current.set(driverId, frameId);
        } else {
          driverAnimationFrameRef.current.delete(driverId);
        }
      };

      const frameId = requestAnimationFrame(tick);
      driverAnimationFrameRef.current.set(driverId, frameId);
    };

    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as {
          type?: string;
          driver_id?: number;
          order_id?: number;
          lat?: number;
          lng?: number;
        };

        if (payload.type !== "driver_location") return;

        const driverId = Number(payload.driver_id);
        const lat = Number(payload.lat);
        const lng = Number(payload.lng);
        const orderId = Number(payload.order_id);

        if (!Number.isFinite(driverId) || !Number.isFinite(lat) || !Number.isFinite(lng) || !Number.isFinite(orderId)) return;
        if (knownDrivers.size > 0 && !knownDrivers.has(driverId)) return;

        const current = featuresRef.current.get(driverId);
        if (!current) {
          const driverName = deliveryUsers?.find((driver) => Number(driver.id) === driverId)?.name ?? `Entregador #${driverId}`;
          featuresRef.current.set(
            driverId,
            buildFeature(
              {
                delivery_user_id: driverId,
                lat,
                lng,
                updated_at: new Date().toISOString(),
                status: "OUT_FOR_DELIVERY",
              },
              driverName,
            ),
          );
          const sourceRef = mapRef.current?.getSource(DELIVERY_SOURCE_ID) as MapboxGeoJSONSource | undefined;
          sourceRef?.setData({ type: "FeatureCollection", features: Array.from(featuresRef.current.values()) });
          return;
        }

        const from = [...current.geometry.coordinates] as LngLatTuple;
        current.properties.updatedAt = new Date().toISOString();
        current.properties.status = "OUT_FOR_DELIVERY";
        smoothMoveDriver(driverId, from, [lng, lat]);
      } catch {
        // no-op
      }
    };

    closeStatusStreamRef.current?.();
    closeStatusStreamRef.current = () => source.close();

    return () => {
      closeStatusStreamRef.current?.();
      closeStatusStreamRef.current = null;
      driverAnimationFrameRef.current.forEach((frameId) => cancelAnimationFrame(frameId));
      driverAnimationFrameRef.current.clear();
    };
  }, [deliveryUsers, tenantId, tenantMismatch]);

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
        const status = payload.status ?? "ONLINE";
        const payloadWithEta = payload as typeof payload & { eta?: string };

        setActiveDriver({
          name: "Entregador em rota",
          status,
          updatedAt: payload.timestamp ?? new Date().toISOString(),
          eta: payloadWithEta.eta,
        });

        if (!driverMarkerRef.current) {
          const marker = new DriverMarker(map, next, status);
          marker.setHeading(payload.heading ?? 0);
          driverMarkerRef.current = marker;
          animatorRef.current = new TrackingAnimator(marker);
          if (followMode) {
            map.easeTo({
              center: next,
              zoom: 15,
              pitch: 55,
              bearing: (payload.heading ?? 0) - 20,
              duration: 900,
            });
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
        marker.setStatus(status);

        const heading = payload.heading ?? headingFromPoints([previous.lng, previous.lat], next);
        marker.setHeading(heading);

        if (followMode) {
          map.easeTo({
            center: next,
            zoom: 15,
            pitch: 55,
            bearing: heading - 20,
            duration: 900,
          });
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
      <MapHeader followMode={followMode} onToggleFollowMode={() => setFollowMode((prev) => !prev)} />

      <div className="rounded-[20px] border border-slate-100 bg-white p-5 shadow-[0_15px_40px_rgba(0,0,0,0.08),0_5px_12px_rgba(0,0,0,0.05)]">
        <div className="relative overflow-hidden rounded-2xl">
          <div ref={containerRef} className="h-[70vh] w-full" />
          <FloatingDriverCard driver={activeDriver} />
        </div>

        <div className="mt-3 space-y-1">
          {tenantId === null ? <p className="text-sm text-red-600">Tenant inválido.</p> : null}
          {tenantMismatch ? <p className="text-sm text-red-600">Tenant não autorizado para o usuário autenticado.</p> : null}
          {mapError ? <p className="text-sm text-red-600">{mapError}</p> : null}
          {isError ? (
            <p className="text-sm text-red-600">
              {error instanceof ApiError ? error.message : "Erro ao carregar localizações de entregadores."}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
