import {
  getApiDeliveryAvailableOrders,
  getApiDeliveryDriverStatus,
  getApiDeliveryOrders,
  postApiDeliveryLocation,
  postApiDeliveryOrderIdStart,
  postApiDeliveryOrdersOrderIdAccept,
  postApiDeliveryOrdersOrderIdComplete,
  postApiDeliveryStatusOffline,
  postApiDeliveryStatusOnline,
  type DeliveryOrder,
} from "@/api/generated";

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

export type DriverBackendStatus = "ONLINE" | "OFFLINE" | "DELIVERING";

function mapOrder(order: DeliveryOrder): AvailableOrder & ActiveOrder {
  return {
    pedido_id: order.id,
    cliente: order.cliente_nome || "Cliente",
    endereco: order.endereco || "",
    distancia_km: 0,
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

export async function getActiveOrders() {
  const data = await getApiDeliveryOrders({ status: "out_for_delivery" });
  return data.map(mapOrder);
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
