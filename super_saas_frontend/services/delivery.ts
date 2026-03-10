import {
  getApiDeliveryAvailableOrders,
  postApiDeliveryLocation,
  postApiDeliveryOrderIdStart,
  postApiDeliveryOrdersOrderIdAccept,
  postApiDeliveryOrdersOrderIdComplete,
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
  distancia_km?: number;
  status?: string;
  destination?: { lat: number; lng: number };
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

export async function getAvailableOrders() {
  const data = await getApiDeliveryAvailableOrders();
  return data.map(mapOrder);
}

export async function acceptOrder(orderId: number | string) {
  await postApiDeliveryOrdersOrderIdAccept(orderId);
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
