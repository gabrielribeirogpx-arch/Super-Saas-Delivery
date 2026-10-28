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
  useEffect(() => {
    const localSalesPreview = ["localhost", "127.0.0.1"].includes(window.location.hostname) &&
      ["/", "/assine", "/onboarding", "/subscriptions", "/continuar", "/entrar"].includes(path ?? "") &&
      /^\d{5,25}$/.test(process.env.NEXT_PUBLIC_META_PIXEL_ID ?? "");
    const allowed = (isSalesAnalyticsPage(window.location.hostname, path ?? "") || localSalesPreview) &&
      (path !== "/" || (process.env.NEXT_PUBLIC_SALES_SITE_ENABLED === "true" && !extractPlatformTenantSlug(window.location.hostname)));
    setEnabled(allowed);
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
  return open ? <aside aria-label="Preferências de medição" className="fixed inset-x-3 bottom-3 z-50 mx-auto max-w-2xl rounded-xl border bg-white p-5 shadow-xl">
    <p className="text-sm">Com sua permissão, usamos o Google Analytics para medir visitas e etapas da contratação e o Pixel da Meta para medir anúncios. Sua escolha não impede o uso do Fomizero.</p>
    <div className="mt-3 flex flex-wrap gap-3"><button className="rounded border px-4 py-2 text-sm" onClick={() => choose(false)}>Recusar medição</button><button className="rounded bg-red-600 px-4 py-2 text-sm text-white" onClick={() => choose(true)}>Aceitar medição</button></div>
  </aside> : <button className="fixed bottom-2 right-3 z-40 rounded border bg-white px-2 py-1 text-xs" onClick={() => setOpen(true)}>Privacidade da medição</button>;
}
