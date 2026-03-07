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
  const data = await getApiDeliveryOrders({ status: "OUT_FOR_DELIVERY" });
  const driverId = getCurrentDriverId();

  const activeStatuses = new Set(["OUT_FOR_DELIVERY", "SAIU", "SAIU_PARA_ENTREGA"]);
  return data
    .filter((order) => {
      const normalizedStatus = String(order.status || "").toUpperCase();
      const isActiveStatus = activeStatuses.has(normalizedStatus);
      const isAssignedToDriver =
        typeof driverId === "number" ? Number(order.assigned_delivery_user_id) === driverId : true;

      return isActiveStatus && isAssignedToDriver;
    })
    .map(mapOrder);
}

function getCurrentDriverId(): number | null {
  if (typeof window === "undefined") {
    return null;
  }

  const rawToken = localStorage.getItem("driver_token") || localStorage.getItem("token");
  if (!rawToken) {
    return null;
  }

  const token = rawToken.startsWith("Bearer ") ? rawToken.slice(7) : rawToken;
  const parts = token.split(".");
  if (parts.length < 2) {
    return null;
  }

  try {
    const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"))) as {
      id?: number | string;
      user_id?: number | string;
      sub?: number | string;
    };

    const rawId = payload.id ?? payload.user_id ?? payload.sub;
    const parsedId = Number(rawId);
    return Number.isFinite(parsedId) ? parsedId : null;
  } catch {
    return null;
  }
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
