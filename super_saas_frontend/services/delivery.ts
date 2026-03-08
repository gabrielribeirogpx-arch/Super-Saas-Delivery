import {
  getApiDeliveryAvailableOrders,
  getApiDeliveryDriverStatus,
  postApiDeliveryLocation,
  postApiDeliveryOrderIdStart,
  postApiDeliveryOrdersOrderIdAccept,
  postApiDeliveryOrdersOrderIdComplete,
  postApiDeliveryStatusOffline,
  postApiDeliveryStatusOnline,
  type DeliveryOrder,
} from "@/api/generated";
import { apiClient } from "@/lib/apiClient";

export type AvailableOrder = {
  pedido_id: number | string;
  endereco: string;
  distancia_km: number;
  cliente?: string;
  destination?: { lat: number; lng: number };
};

export type ActiveOrder = {
  pedido_id: number | string;
  cliente: string;
  endereco: string;
  distancia_km?: number;
  status?: string;
  destination?: { lat: number; lng: number };
};

export type DriverBackendStatus = "ONLINE" | "OFFLINE" | "DELIVERING";

type ActiveDeliveryApiResponse = {
  id: number | string;
  status?: string;
  customer_name?: string;
  address?: string;
  distance_km?: number;
  assigned_delivery_user_id?: number | string;
} | null;

type DriverDeliverySnapshotResponse = {
  driver?: {
    id?: number | string;
    status?: string;
    tenant_id?: number | string;
  };
  active_delivery?: ActiveDeliveryApiResponse;
  out_for_delivery_count?: number;
  server_time?: string;
};

export type DriverDeliverySnapshot = {
  driverStatus: DriverBackendStatus;
  activeOrder: ActiveOrder | null;
  outForDeliveryCount: number;
  serverTime?: string;
};

function mapOrder(order: DeliveryOrder): AvailableOrder & ActiveOrder {
  return {
    pedido_id: order.id,
    cliente: order.cliente_nome || "Cliente",
    endereco: order.endereco || "",
    status: order.status,
    distancia_km: 0,
  };
}

function mapActiveOrder(payload: ActiveDeliveryApiResponse | undefined): ActiveOrder | null {
function mapActiveOrder(payload: ActiveDeliveryApiResponse): ActiveOrder | null {
  if (!payload) {
    return null;
  }

  return {
    pedido_id: payload.id,
    cliente: payload.customer_name || "Cliente",
    endereco: payload.address || "",
    distancia_km: payload.distance_km,
    status: payload.status,
  };
}

function normalizeDriverStatus(status: string | undefined): DriverBackendStatus {
  const normalizedStatus = String(status ?? "OFFLINE").toUpperCase();

  if (normalizedStatus === "ONLINE" || normalizedStatus === "DELIVERING") {
    return normalizedStatus;
  }

  return "OFFLINE";
}

export async function getDriverBackendStatus(): Promise<DriverBackendStatus> {
  const response = await getApiDeliveryDriverStatus();
  return normalizeDriverStatus(response.status);
}

export async function setDriverOnline() {
  await postApiDeliveryStatusOnline();
}

export async function setDriverOffline() {
  await postApiDeliveryStatusOffline();
}

export async function ensureDriverOnline() {
  let status = await getDriverBackendStatus();
  console.debug("Driver online status from backend:", status);

  if (status === "OFFLINE") {
    await setDriverOnline();
    status = await getDriverBackendStatus();
    console.debug("Driver online status from backend:", status);
  }

  return status;
}

export async function getAvailableOrders() {
  const data = await getApiDeliveryAvailableOrders();
  return data.map(mapOrder);
}

export async function acceptOrder(orderId: number | string) {
  await postApiDeliveryOrdersOrderIdAccept(orderId);
}

export async function getDriverState() {
  return apiClient("/api/delivery/driver/state", {
    cache: "no-store",
  });
}

export async function getDriverDeliverySnapshot(): Promise<DriverDeliverySnapshot> {
  const response = await apiClient("/api/delivery/driver/snapshot", {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch driver snapshot: ${response.status}`);
  }

  const data = (await response.json()) as DriverDeliverySnapshotResponse;

  return {
    driverStatus: normalizeDriverStatus(data.driver?.status),
    activeOrder: mapActiveOrder(data.active_delivery),
    outForDeliveryCount: Number(data.out_for_delivery_count || 0),
    serverTime: data.server_time,
  };
}

export async function getActiveDelivery(): Promise<ActiveOrder | null> {
  const response = await apiClient("/api/delivery/driver/active");

  if (!response.ok) {
    throw new Error(`Failed to fetch active delivery: ${response.status}`);
  }

  const data = (await response.json()) as ActiveDeliveryApiResponse;
  return mapActiveOrder(data);
}

export async function startOrder(orderId: number | string) {
  await postApiDeliveryOrderIdStart(orderId);
}

export async function completeOrder(orderId: number | string) {
  await postApiDeliveryOrdersOrderIdComplete(orderId);
}

export async function sendDriverLocation(lat: number, lng: number, orderId?: number | string) {
  if (!orderId) {
    return;
  }

  await postApiDeliveryLocation({ lat, lng, order_id: Number(orderId) });
}
