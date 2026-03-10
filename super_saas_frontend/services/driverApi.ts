import { api } from "@/lib/api";

export type DriverOrder = {
  id: number;
  status: string;
  raw_status?: string;
  customer_name: string;
  address: string;
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

export async function sendDriverLocation(payload: { order_id: number; lat: number; lng: number }) {
  return api.post("/api/driver/location", payload);
}
