import type { SubscriptionOffer } from "./subscriptions";
export type SalesConfig = {
  ready: boolean; site_key: string; terms_url: string; privacy_url: string;
  terms_version: string; support_email: string; offers: SubscriptionOffer[];
};
export function selectedPlan(value: string | null): string | null {
  return value && /^[a-z][a-z0-9_]{0,49}$/.test(value) ? value : null;
}
export function safeLocalRedirect(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || /[\\\u0000-\u0020]/.test(value)) return "/dashboard";
  try { return new URL(value, "https://fomizero.invalid").origin === "https://fomizero.invalid" ? value : "/dashboard"; }
  catch { return "/dashboard"; }
}
