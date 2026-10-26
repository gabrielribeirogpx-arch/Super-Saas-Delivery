export const ORDER_WHATSAPP_TEMPLATES = {
  pending: "Olá, {cliente}! Recebemos o seu pedido #{pedido}. Em breve iniciaremos o atendimento.",
  confirmed: "Olá, {cliente}! Seu pedido #{pedido} foi confirmado.",
  preparing: "Olá, {cliente}! Seu pedido #{pedido} já está sendo preparado.",
  ready: "Olá, {cliente}! Seu pedido #{pedido} está pronto.",
  out_for_delivery: "Olá, {cliente}! Seu pedido #{pedido} saiu para entrega.",
  delivered: "Olá, {cliente}! Seu pedido #{pedido} foi entregue. Obrigado pela preferência!",
  cancelled: "Olá, {cliente}. Informamos que o pedido #{pedido} foi cancelado.",
} as const;

export type OrderWhatsAppStatus = keyof typeof ORDER_WHATSAPP_TEMPLATES;

export type OrderWhatsAppTemplateContext = Partial<Record<
  "cliente" | "pedido" | "status" | "total" | "loja" | "previsao" | "endereco",
  string | number | null | undefined
>>;

export interface OrderWhatsAppPayload {
  id: number;
  daily_order_number?: number | null;
  cliente_nome?: string | null;
  cliente_telefone?: string | null;
  customer_name?: string | null;
  customer_phone?: string | null;
  status?: string | null;
  valor_total?: number | null;
  total_cents?: number | null;
  endereco?: string | null;
  estimated_delivery_time?: string | null;
  estimated_preparation_time?: string | null;
}

const KNOWN_VARIABLES = new Set(["cliente", "pedido", "status", "total", "loja", "previsao", "endereco"]);

const STATUS_ALIASES: Record<string, OrderWhatsAppStatus> = {
  RECEBIDO: "pending",
  PENDING: "pending",
  CONFIRMADO: "confirmed",
  CONFIRMED: "confirmed",
  EM_PREPARO: "preparing",
  PREPARANDO: "preparing",
  PREPARING: "preparing",
  PRONTO: "ready",
  READY: "ready",
  SAIU: "out_for_delivery",
  SAIU_PARA_ENTREGA: "out_for_delivery",
  OUT_FOR_DELIVERY: "out_for_delivery",
  ENTREGUE: "delivered",
  DELIVERED: "delivered",
  CANCELADO: "cancelled",
  CANCELLED: "cancelled",
  CANCELED: "cancelled",
};

export function normalizeOrderWhatsAppStatus(status?: string | null): OrderWhatsAppStatus {
  const normalized = (status || "").trim().toUpperCase();
  return STATUS_ALIASES[normalized] ?? "pending";
}

export function getOrderWhatsAppTemplate(status?: string | null) {
  return ORDER_WHATSAPP_TEMPLATES[normalizeOrderWhatsAppStatus(status)];
}

export function normalizeWhatsAppPhone(phone?: string | null) {
  const digits = String(phone ?? "").replace(/\D/g, "");

  if (!digits) return null;
  if (digits.startsWith("55") && (digits.length === 12 || digits.length === 13)) return digits;
  if (digits.length === 10 || digits.length === 11) return `55${digits}`;

  return null;
}

export function renderOrderWhatsAppMessage(template: string, context: OrderWhatsAppTemplateContext) {
  return template.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, (match, variable: string) => {
    if (!KNOWN_VARIABLES.has(variable)) return match;
    const value = context[variable as keyof OrderWhatsAppTemplateContext];
    if (value === null || value === undefined) return "";
    return String(value);
  });
}

export function formatOrderTotal(cents?: number | null) {
  if (typeof cents !== "number" || !Number.isFinite(cents)) return "";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(cents / 100);
}

export function buildOrderWhatsAppContext(order: OrderWhatsAppPayload, storeName?: string | null): OrderWhatsAppTemplateContext {
  const totalCents = typeof order.total_cents === "number" && order.total_cents > 0 ? order.total_cents : order.valor_total;
  return {
    cliente: order.customer_name || order.cliente_nome || "cliente",
    pedido: order.daily_order_number ?? order.id,
    status: order.status || "",
    total: formatOrderTotal(totalCents),
    loja: storeName || "",
    previsao: order.estimated_delivery_time || order.estimated_preparation_time || "",
    endereco: order.endereco || "",
  };
}

export function buildOrderWhatsAppUrl(order: OrderWhatsAppPayload, template = getOrderWhatsAppTemplate(order.status), storeName?: string | null) {
  const phone = normalizeWhatsAppPhone(order.customer_phone || order.cliente_telefone);
  if (!phone) return null;

  const message = renderOrderWhatsAppMessage(template, buildOrderWhatsAppContext(order, storeName));
  return `https://wa.me/${phone}?text=${encodeURIComponent(message)}`;
}

export function openOrderWhatsApp(order: OrderWhatsAppPayload, template = getOrderWhatsAppTemplate(order.status), storeName?: string | null) {
  const url = buildOrderWhatsAppUrl(order, template, storeName);
  if (!url || typeof window === "undefined") return false;
  window.open(url, "_blank", "noopener,noreferrer");
  return true;
}
