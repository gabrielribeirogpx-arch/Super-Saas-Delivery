import type { ApiError } from "@/services/api";
import { api } from "@/services/api";

export type DeliveryLoginPayload = {
  email: string;
  password: string;
};

export type DeliveryLoginResponse = {
  access_token?: string;
  token?: string;
  token_type?: string;
};

export type DeliveryOrder = {
  id: number;
  tenant_id?: number;
  status?: string;
  cliente_nome?: string;
  cliente_telefone?: string;
  itens?: unknown;
  endereco?: string;
  observacao?: string;
  ready_at?: string | null;
  start_delivery_at?: string | null;
  assigned_delivery_user_id?: number | null;
  created_at?: string | null;
};

export type DeliveryActionResponse = {
  ok?: boolean;
  status?: string;
  assigned_delivery_user_id?: number;
};

export type DeliveryLocationPayload = {
  order_id: number;
  lat: number;
  lng: number;
};

export type GeneratedApiError = ApiError;

export async function postApiDeliveryAuthLogin(data: DeliveryLoginPayload) {
  const response = await api.post<DeliveryLoginResponse>("/api/delivery/auth/login", data);
  return response.data;
}

export async function postApiDeliveryStatusOnline() {
  const response = await api.post<Record<string, unknown>>("/api/delivery/status/online");
  return response.data;
}

export async function postApiDeliveryStatusOffline() {
  const response = await api.post<Record<string, unknown>>("/api/delivery/status/offline");
  return response.data;
}

export async function getApiDeliveryOrders(params?: { status?: string }) {
  const response = await api.get<DeliveryOrder[]>("/api/delivery/orders", { params });
  return response.data;
}

export async function getApiDeliveryAvailableOrders() {
  const response = await api.get<DeliveryOrder[]>("/api/delivery/available-orders");
  return response.data;
}

export async function postApiDeliveryOrdersOrderIdAccept(orderId: number | string) {
  const response = await api.post<Record<string, unknown>>(`/api/delivery/orders/${orderId}/accept`);
  return response.data;
}

export async function postApiDeliveryOrderIdStart(orderId: number | string) {
  const response = await api.post<DeliveryActionResponse>(`/api/delivery/${orderId}/start`);
  return response.data;
}

export async function postApiDeliveryOrdersOrderIdComplete(orderId: number | string) {
  const response = await api.post<DeliveryActionResponse>(`/api/delivery/orders/${orderId}/complete`);
  return response.data;
}

export async function postApiDeliveryLocation(data: DeliveryLocationPayload) {
  const response = await api.post<Record<string, unknown>>("/api/delivery/location", data);
  return response.data;
}
