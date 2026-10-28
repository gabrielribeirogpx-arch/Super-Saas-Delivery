import { advertisingConsent } from "@/lib/metaPixel";

const measurementId = "G-HDBVG6L1NT";
const platformHost = "www.fomizero.com.br";
const salesPaths = new Set(["/", "/assine", "/onboarding", "/continuar", "/entrar", "/subscriptions"]);
type Gtag = (...args: unknown[]) => void;
declare global { interface Window { dataLayer?: unknown[]; gtag?: Gtag } }

let started = false;
let ready = false;
let configured = false;
let lastView = "";

export function isSalesAnalyticsPage(hostname: string, pathname: string): boolean {
  // Keep GA4 off tenant hosts, including their subscription and customer pages.
  return hostname === platformHost && salesPaths.has(pathname);
}

function canMeasure(): boolean {
  return advertisingConsent() && !window.location.hash &&
    isSalesAnalyticsPage(window.location.hostname, window.location.pathname);
}

function sendPageView() {
  if (!ready || !configured || !canMeasure()) return;
  // Strip query and fragment: they may contain campaign details or invitation tokens.
  const pagePath = window.location.pathname;
  const view = window.location.hostname + pagePath;
  if (lastView === view) return;
  lastView = view;
  window.gtag?.("event", "page_view", {
    page_location: window.location.origin + pagePath,
    page_path: pagePath,
    page_title: document.title,
  });
}

function activateAnalytics() {
  if (!ready || !canMeasure()) return;
  window.gtag?.("consent", "update", { analytics_storage: "granted" });
  if (!configured) {
    window.gtag?.("config", measurementId, { send_page_view: false });
    configured = true;
  }
  sendPageView();
}

export function loadSalesAnalytics(): void {
  if (!canMeasure()) return;
  if (started) {
    activateAnalytics();
    return;
  }
  started = true;
  window.dataLayer = window.dataLayer || [];
  window.gtag = (...args: unknown[]) => { window.dataLayer?.push(args); };
  window.gtag("js", new Date());
  window.gtag("consent", "default", {
    analytics_storage: "denied", ad_storage: "denied",
    ad_user_data: "denied", ad_personalization: "denied",
  });
  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${measurementId}`;
  script.onload = () => {
    ready = true;
    activateAnalytics();
  };
  document.head.appendChild(script);
}

export function revokeSalesAnalytics(): void {
  window.gtag?.("consent", "update", { analytics_storage: "denied" });
}

export function trackSalesAnalyticsEvent(
  name: "sign_up" | "begin_checkout",
  plan?: { code: string; price_cents: number },
): void {
  if (!canMeasure() || !configured) return;
  window.gtag?.("event", name, {
    ...(plan ? { currency: "BRL", value: plan.price_cents / 100, plan: plan.code } : {}),
    transport_type: "beacon",
  });
}
