type Meta = ((...args: unknown[]) => void) & { queue: unknown[][]; loaded: boolean; version: string; callMethod?: (...args: unknown[]) => void };
declare global { interface Window { fbq?: Meta; _fbq?: Meta } }
const consentKey = "fomizero:advertising-consent:v1";
export function advertisingConsent(): boolean {
  try { return localStorage.getItem(consentKey) === "yes"; } catch { return false; }
}
export function setAdvertisingConsent(allowed: boolean) {
  try { localStorage.setItem(consentKey, allowed ? "yes" : "no"); } catch { /* Browsers may block storage. */ }
  window.fbq?.("consent", allowed ? "grant" : "revoke");
  window.dispatchEvent(new Event("fomizero:advertising-consent"));
}
export function consentChoice(): boolean {
  try { return localStorage.getItem(consentKey) !== null; } catch { return false; }
}
export function loadMetaPixel() {
  const id = process.env.NEXT_PUBLIC_META_PIXEL_ID ?? "";
  if (!advertisingConsent() || !/^\d{5,25}$/.test(id) || window.location.hash) return false;
  if (!window.fbq) {
    const fbq: Meta = Object.assign((...args: unknown[]) => { if (fbq.callMethod) fbq.callMethod(...args); else fbq.queue.push(args); }, { queue: [] as unknown[][], loaded: true, version: "2.0" });
    window.fbq = fbq; window._fbq = fbq;
    fbq("consent", "grant"); fbq("set", "autoConfig", false, id); fbq("init", id);
    const script = document.createElement("script"); script.async = true;
    script.src = "https://connect.facebook.net/en_US/fbevents.js"; script.dataset.fomizeroMeta = "1";
    document.head.appendChild(script);
  }
  return true;
}
// A closed event list prevents payment URLs/return pages from inventing a Purchase.
export function trackSalesEvent(event: "CompleteRegistration" | "InitiateCheckout", plan?: { code: string; price_cents: number }) {
  try {
    if (event === "InitiateCheckout" && process.env.NEXT_PUBLIC_META_CHECKOUT_SOURCE !== "fomizero") return;
    if (!loadMetaPixel()) return;
    window.fbq?.("track", event, plan ? { content_ids: [plan.code], content_type: "product", value: plan.price_cents / 100, currency: "BRL" } : { status: true });
  } catch { /* Advertising failures must never interrupt enrollment or checkout. */ }
}
