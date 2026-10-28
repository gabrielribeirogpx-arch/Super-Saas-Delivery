"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { extractPlatformTenantSlug } from "@/lib/platformDomains";
import { useRef } from "react";
import { advertisingConsent, consentChoice, loadMetaPixel, setAdvertisingConsent } from "@/lib/metaPixel";
import { isSalesAnalyticsPage, loadSalesAnalytics, revokeSalesAnalytics } from "@/lib/salesAnalytics";
export default function AdvertisingConsent() {
  const path = usePathname();
  const lastView = useRef("");
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);
  useEffect(() => {
    const googlePage = isSalesAnalyticsPage(window.location.hostname, path ?? "");
    const localSalesPreview = ["localhost", "127.0.0.1"].includes(window.location.hostname) &&
      ["/", "/assine", "/onboarding", "/subscriptions", "/continuar", "/entrar"].includes(path ?? "") &&
      /^\d{5,25}$/.test(process.env.NEXT_PUBLIC_META_PIXEL_ID ?? "");
    const tenantSubscription = path === "/subscriptions" && Boolean(extractPlatformTenantSlug(window.location.hostname)) &&
      /^\d{5,25}$/.test(process.env.NEXT_PUBLIC_META_PIXEL_ID ?? "");
    const allowed = (googlePage || tenantSubscription || localSalesPreview) &&
      (path !== "/" || (process.env.NEXT_PUBLIC_SALES_SITE_ENABLED === "true" && !extractPlatformTenantSlug(window.location.hostname)));
    setEnabled(allowed);
    setGoogleEnabled(googlePage);
    if (!allowed) { revokeSalesAnalytics(); return; }
    const update = () => {
      if (!advertisingConsent()) { revokeSalesAnalytics(); return; }
      loadSalesAnalytics();
      if (loadMetaPixel() && lastView.current !== path) {
        window.fbq?.("track", "PageView");
        lastView.current = path ?? "";
      }
    };
    setOpen(!consentChoice()); update();
    window.addEventListener("fomizero:advertising-consent", update);
    return () => {
      window.removeEventListener("fomizero:advertising-consent", update);
      revokeSalesAnalytics();
    };
  }, [path]);
  if (!enabled) return null;
  const choose = (allowed: boolean) => { setAdvertisingConsent(allowed); setOpen(false); };
  return open ? <aside aria-label="Preferências de medição" className="fixed bottom-3 left-3 right-3 z-50 rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-md sm:left-auto sm:right-4 sm:w-[440px]">
    <p className="text-xs leading-snug text-slate-600">{googleEnabled ? "Google Analytics e Meta só com sua permissão." : "Meta só com sua permissão."} <a className="font-semibold text-red-700 underline underline-offset-2" href="https://fomizero.com.br/privacidade/" target="_blank" rel="noopener noreferrer">Detalhes</a></p>
    <div className="mt-2 flex gap-2"><button className="min-h-9 flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold" onClick={() => choose(false)}>Recusar medição</button><button className="min-h-9 flex-1 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white" onClick={() => choose(true)}>Aceitar medição</button></div>
  </aside> : <button className="fixed bottom-2 right-3 z-40 rounded border bg-white px-2 py-1 text-xs" onClick={() => setOpen(true)}>Privacidade da medição</button>;
}
