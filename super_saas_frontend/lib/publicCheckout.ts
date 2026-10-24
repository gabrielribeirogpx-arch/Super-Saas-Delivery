import { requireStorefrontTenant, storefrontFetch } from "./storefrontApi.ts";
import { OrderAttemptError, UnconfirmedOrderAttemptError, orderAttempt, rejectFirstOrderAttempt, rememberOrderResponse } from "./orderAttempt.ts";
export { completeOrderAttempt, startNewOrderAttempt } from "./orderAttempt.ts";

const PUBLIC_ORDER_ENDPOINT = "/public/orders";
const PUBLIC_ORDER_ERROR_MESSAGE = "Não foi possível confirmar o pedido. Tente novamente sem alterar os dados para consultar a mesma tentativa.";

export class PublicOrderSubmissionError extends Error {}
export class PublicOrderReviewRequiredError extends PublicOrderSubmissionError {}

export type SubmissionLock = { current: boolean };

export function tryBeginPublicOrderSubmission(lock: SubmissionLock) {
  if (lock.current) return false;
  lock.current = true;
  return true;
}

export function endPublicOrderSubmission(lock: SubmissionLock) {
  lock.current = false;
}

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
  const attempt = await orderAttempt(resolvedTenant, payload).catch(error => {
    if (error instanceof UnconfirmedOrderAttemptError) throw new PublicOrderReviewRequiredError(error.message);
    if (error instanceof OrderAttemptError) throw new PublicOrderSubmissionError(error.message);
    throw error;
  });

  const response = await storefrontFetch(PUBLIC_ORDER_ENDPOINT, {
    credentials: "include",
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": attempt.key },
    body: JSON.stringify(payload),
  }, resolvedTenant);

  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    if (response.status === 409) throw new PublicOrderReviewRequiredError("Esta tentativa não pôde ser confirmada. Confira seus pedidos com a loja antes de fazer outro pedido.");
    rejectFirstOrderAttempt(resolvedTenant, attempt, response.status);
    const errorMessage = isRecord(data)
      ? String(data.message ?? data.detail ?? "Não foi possível enviar o pedido")
      : "Não foi possível enviar o pedido";
    throw new Error(errorMessage);
  }

  if (!isRecord(data) || !isNonEmptyString(data.tracking_token)) {
    throw new PublicOrderReviewRequiredError(PUBLIC_ORDER_ERROR_MESSAGE);
  }
  rememberOrderResponse(data, resolvedTenant, attempt);

  return data as TResponse;
}

export { PUBLIC_ORDER_ENDPOINT, PUBLIC_ORDER_ERROR_MESSAGE };
