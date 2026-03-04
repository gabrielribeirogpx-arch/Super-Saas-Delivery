import { api } from "@/services/api";

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
  destination?: { lat: number; lng: number };
};

export async function setDriverOnline() {
  await api.post("/api/delivery/status/online");
}

export async function setDriverOffline() {
  await api.post("/api/delivery/status/offline");
}

export async function getAvailableOrders() {
  const { data } = await api.get<AvailableOrder[]>("/api/delivery/available-orders");
  return data;
}

export async function acceptOrder(orderId: number | string) {
  await api.post(`/api/delivery/orders/${orderId}/accept`);
}

export async function getActiveOrders() {
  const { data } = await api.get<ActiveOrder[]>("/api/delivery/orders");
  return data;
}

export async function startOrder(orderId: number | string) {
  await api.post(`/api/delivery/orders/${orderId}/start`);
}

export async function completeOrder(orderId: number | string) {
  await api.post(`/api/delivery/orders/${orderId}/complete`);
}

export async function sendDriverLocation(lat: number, lng: number) {
  await api.post("/api/delivery/location", { lat, lng });
}
