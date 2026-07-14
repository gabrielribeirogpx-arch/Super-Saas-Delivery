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
  destination_lat?: number | null;
  destination_lng?: number | null;
  phone?: string | null;
  neighborhood?: string | null;
  complement?: string | null;
  reference?: string | null;
  notes?: string | null;
  payment_method?: string | null;
  change_for?: string | number | null;
  order_type?: string | null;
  total_cents?: number | null;
  items?: string | null;
  created_at?: string | null;
};

export type DriverState = {
  driver: { id: number; name: string; email: string; restaurant_id: number; role: string };
  active_delivery: DriverOrder | null;
  available_orders: DriverOrder[];
  assigned_orders?: DriverOrder[];
  completed_today?: number;
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

export type DriverLocationPayload = { order_id?: number; lat?: number; lng?: number; delivery_id?: number; latitude?: number; longitude?: number; accuracy?: number | null; speed?: number | null; heading?: number | null; recorded_at?: string };

export async function sendDriverLocation(payload: DriverLocationPayload) {
  const deliveryId = payload.delivery_id ?? payload.order_id;
  const latitude = payload.latitude ?? payload.lat;
  const longitude = payload.longitude ?? payload.lng;
  if (!Number.isFinite(deliveryId) || !Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    throw new Error("Invalid location payload");
  }

  return api.post(`/api/driver/deliveries/${deliveryId}/location`, {
    delivery_id: deliveryId,
    latitude,
    longitude,
    accuracy: payload.accuracy,
    speed: payload.speed,
    heading: payload.heading,
    recorded_at: payload.recorded_at,
  });
}
