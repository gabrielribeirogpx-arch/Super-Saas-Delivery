export function paymentMethodLabel(method?: string | null) {
  const value = (method ?? "").trim().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  if (["cash", "money", "dinheiro"].includes(value)) return "Dinheiro";
  if (["pix", "manual_pix"].includes(value)) return "Pix direto da loja";
  if (["card", "cartao", "credito", "debito", "external_card"].includes(value)) return "Cartão com a loja";
  if (value === "native_pix") return "Pix online";
  if (value === "native_card") return "Cartão online";
  return method || "Não informado";
}

export function paymentStatusLabel(status: string) {
  return ({ pending: "Pendente", paid: "Recebido", canceled: "Cancelado", refunded: "Devolvido" } as Record<string, string>)[status] ?? status;
}

export function canManagePayments(role?: string | null) {
  return ["owner", "admin", "cashier"].includes((role ?? "").trim().toLowerCase());
}

export function formatBRL(cents: number) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(cents / 100);
}
