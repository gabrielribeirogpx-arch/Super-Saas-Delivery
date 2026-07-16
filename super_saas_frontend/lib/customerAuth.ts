import { storefrontFetch } from "@/lib/storefrontApi";
export async function requestCustomerCode(phone: string, accepted_terms = true) {
  const r = await storefrontFetch("/api/public/customer-auth/request-code", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ phone, accepted_terms }) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || "Não foi possível enviar o código");
  return data;
}
export async function verifyCustomerCode(phone: string, code: string) {
  const r = await storefrontFetch("/api/public/customer-auth/verify-code", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ phone, code }) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || "Código inválido");
  return data;
}
export async function customerMe() { const r = await storefrontFetch("/api/public/customer-auth/me", { credentials: "include" }); if (!r.ok) return null; return r.json(); }
export async function customerOrders() { const r = await storefrontFetch("/api/public/customer-auth/orders", { credentials: "include" }); if (!r.ok) throw new Error("Entre para ver pedidos"); return r.json(); }
export async function logoutCustomer() { await storefrontFetch("/api/public/customer-auth/logout", { method: "POST", credentials: "include" }); }
