import { api } from "@/lib/api";

export type DriverOrder = {
  id: number;
  status: string;
  daily_order_number?: number | null;
  raw_status?: string;
  customer_name: string;
  address: string;
  customer_lat?: number | null;
  customer_lng?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  destination?: { lat?: number | null; lng?: number | null } | null;
  created_at?: string | null;
};

export type DriverState = {
  driver: { id: number; name: string; email: string; restaurant_id: number; role: string };
  active_delivery: DriverOrder | null;
  available_orders: DriverOrder[];
};

export async function driverLogin(email: string, password: string) {
  return api.post<{ token: string; driver: DriverState["driver"] }>("/api/driver/auth/login", { email, password });
}

export async function getDriverState() {
  return api.get<DriverState>("/api/driver/state");
}

export async function acceptOrder(orderId: number) {
  return api.post(`/api/driver/orders/${orderId}/accept`);
}

export async function startOrder(orderId: number) {
  return api.post(`/api/driver/orders/${orderId}/start`);
}

export async function completeOrder(orderId: number) {
  return api.post(`/api/driver/orders/${orderId}/complete`);
}

export type DriverLocationPayload = { order_id: number; lat: number; lng: number };

export async function sendDriverLocation(payload: DriverLocationPayload) {
  if (!Number.isFinite(payload.order_id) || !Number.isFinite(payload.lat) || !Number.isFinite(payload.lng)) {
    throw new Error("Invalid location payload");
  }

  return api.post("/api/driver/location", payload);
}
