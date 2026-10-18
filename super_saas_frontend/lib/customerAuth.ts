import { storefrontFetch, resolveStorefrontTenant } from "@/lib/storefrontApi";
import { clearCustomerTrackingData } from "@/lib/orderTrackingCache";

export function customerTenant() {
  if (typeof window === "undefined") return "";
  return resolveStorefrontTenant() || new URLSearchParams(window.location.search).get("tenant") || "";
}
export function customerAccountUrl(path: string) {
  const tenant = customerTenant();
  return tenant ? `${path}?tenant=${encodeURIComponent(tenant)}` : path;
}
async function authRequest(path: string, body?: object) {
  const response = await storefrontFetch(`/api/public/customer-auth/${path}`, {
    method: body ? "POST" : "GET", credentials: "include", cache: "no-store",
    ...(body ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}),
  }, customerTenant());
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Não foi possível acessar sua conta");
  return data;
}
export const requestCustomerCode = (phone: string, accepted_terms = false) => authRequest("request-code", { phone, accepted_terms });
export async function verifyCustomerCode(phone: string, code: string) {
  const data = await authRequest("verify-code", { phone, code });
  // Do not keep the previous person's order shortcuts after an account switch.
  clearCustomerTrackingData();
  return data;
}
export async function customerMe() {
  try { return await authRequest("me"); } catch { return null; }
}
export const customerOrders = () => authRequest("orders");
export async function logoutCustomer() {
  // Clear local shortcuts even when the server is unreachable, and report a
  // failed logout rather than pretending the HttpOnly cookie was removed.
  try { await authRequest("logout", {}); } finally { clearCustomerTrackingData(); }
}
