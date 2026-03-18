import { requireStorefrontTenant, storefrontFetch } from "@/lib/storefrontApi";

const PUBLIC_ORDER_ENDPOINT = "/public/orders";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNonEmptyString(value: unknown) {
  return typeof value === "string" && value.trim().length > 0;
}

export function validatePublicOrderPayload(payload: unknown) {
  if (!isRecord(payload)) {
    throw new Error("Payload de checkout inválido");
  }

  const items = Array.isArray(payload.items) ? payload.items : [];
  if (items.length === 0) {
    throw new Error("Carrinho vazio");
  }

  if (!isNonEmptyString(payload.customer_phone)) {
    throw new Error("Telefone do cliente é obrigatório");
  }

  const deliveryType = String(payload.delivery_type ?? payload.order_type ?? "").trim().toUpperCase();
  const deliveryAddress = isRecord(payload.delivery_address) ? payload.delivery_address : null;

  if (deliveryType === "ENTREGA" || String(payload.order_type ?? "").trim().toLowerCase() === "delivery") {
    const zip = String(deliveryAddress?.zip ?? deliveryAddress?.cep ?? payload.cep ?? "").trim();
    const street = String(deliveryAddress?.street ?? payload.street ?? "").trim();
    const number = String(deliveryAddress?.number ?? payload.number ?? "").trim();
    const neighborhood = String(deliveryAddress?.neighborhood ?? payload.neighborhood ?? "").trim();
    const city = String(deliveryAddress?.city ?? payload.city ?? "").trim();
    const state = String(deliveryAddress?.state ?? payload.state ?? "").trim();

    if (!zip || !street || !number || !neighborhood || !city || !state) {
      throw new Error("Endereço de entrega incompleto");
    }
  }
}

export async function submitPublicOrder<TResponse = unknown>(payload: unknown, tenant?: string | null) {
  const resolvedTenant = requireStorefrontTenant(tenant);
  validatePublicOrderPayload(payload);

  const response = await storefrontFetch(PUBLIC_ORDER_ENDPOINT, {
    credentials: "include",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }, resolvedTenant);

  let data: TResponse | { message?: string; detail?: string } | null = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const errorMessage = isRecord(data)
      ? String(data.message ?? data.detail ?? "Não foi possível enviar o pedido")
      : "Não foi possível enviar o pedido";
    throw new Error(errorMessage);
  }

  return data as TResponse;
}

export { PUBLIC_ORDER_ENDPOINT };
