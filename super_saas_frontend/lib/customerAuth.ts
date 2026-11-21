import { storefrontFetch, resolveStorefrontTenant } from "@/lib/storefrontApi";
import type { CheckoutCustomerProfile } from "@/lib/checkoutCustomerProfile";
import { clearCustomerTrackingData } from "@/lib/orderTrackingCache";

export function customerTenant() {
  if (typeof window === "undefined") return "";
  return resolveStorefrontTenant() || new URLSearchParams(window.location.search).get("tenant") || "";
}
export function customerAccountUrl(path: string) {
  const tenant = customerTenant();
  return tenant ? `${path}?tenant=${encodeURIComponent(tenant)}` : path;
}
async function authRequest(path: string, body?: object, tenant = customerTenant(), signal?: AbortSignal) {
  const response = await storefrontFetch(`/api/public/customer-auth/${path}`, {
    method: body ? "POST" : "GET", credentials: "include", cache: "no-store", signal,
    ...(body ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}),
  }, tenant);
  const data = await response.json().catch(() => ({}));
  if (path === "me" && response.status === 401) return null;
  if (path === "checkout-profile" && [401, 403].includes(response.status)) return null;
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Não foi possível acessar sua conta");
  return data;
}
export const requestCustomerCode = (phone: string, accepted_terms = false) => authRequest("request-code", { phone, accepted_terms });
export const requestCustomerEmailCode = (email: string, accepted_terms = false, contact?: { name: string; phone: string }) =>
  authRequest("request-email-code", { email, accepted_terms, ...contact });
export async function verifyCustomerEmailCode(email: string, code: string) {
  const data = await authRequest("verify-email-code", { email, code });
  clearCustomerTrackingData();
  return data;
}
export async function verifyCustomerCode(phone: string, code: string) {
  const data = await authRequest("verify-code", { phone, code });
  // Do not keep the previous person's order shortcuts after an account switch.
  clearCustomerTrackingData();
  return data;
}
export async function customerMe() {
  return authRequest("me");
}
export async function customerCheckoutProfile(tenant: string, signal: AbortSignal): Promise<CheckoutCustomerProfile | null> {
  const profile = await authRequest("checkout-profile", undefined, tenant, signal);
  if (!profile?.phone || !Array.isArray(profile.addresses)) return null;
  return {
    ...profile,
    addresses: (profile.addresses as CheckoutCustomerProfile["addresses"]).filter(
      (address) => (address.cep || address.zip)?.replace(/\D/g, "").length === 8
        && address.street && address.number && address.neighborhood && address.city && address.state,
    ),
  };
}
export const customerOrders = () => authRequest("orders");
export async function logoutCustomer() {
  // Clear local shortcuts even when the server is unreachable, and report a
  // failed logout rather than pretending the HttpOnly cookie was removed.
  try { await authRequest("logout", {}); } finally { clearCustomerTrackingData(); }
}
