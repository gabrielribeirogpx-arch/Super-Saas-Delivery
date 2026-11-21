"use client";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { extractPlatformTenantSlug } from "@/lib/platformDomains";
import DriverPwaStatus from "./DriverPwaStatus";
import RetireDriverPwa from "./RetireDriverPwa";
import CustomerPwaHeadLinks from "./CustomerPwaHeadLinks";
import CustomerPwaUpdatePrompt from "./CustomerPwaUpdatePrompt";
export default function AppPwaFeatures() {
  const path = usePathname(); const [tenant, setTenant] = useState<boolean | null>(null);
  useEffect(() => { setTenant(Boolean(extractPlatformTenantSlug(window.location.hostname))); }, []);
  if (tenant === null || ["/assine", "/onboarding", "/entrar", "/continuar", "/verificar-email", "/esqueci-senha", "/redefinir-senha", "/baixar-entregador", "/baixar-entregador/"].includes(path ?? "") ||
    (path === "/" && process.env.NEXT_PUBLIC_SALES_SITE_ENABLED === "true" && !tenant)) return null;
  const adminRoute = /^\/(dashboard|orders|kds|finance|inventory|reports|menu|storefront-preview|storefront-preview-frame|whatsapp|ai|marketing|minha-loja|customers|users|audit|subscriptions|settings|profile|admin|install-app)(\/|$)/.test(path ?? "");
  if (adminRoute) return null;
  const driverRoute = path === "/driver" || Boolean(path?.startsWith("/driver/"));
  if (driverRoute) {
    const recoveryRoute = path === "/driver/esqueci-senha" || path === "/driver/redefinir-senha";
    return <><RetireDriverPwa />{!recoveryRoute && <DriverPwaStatus />}</>;
  }
  return <><CustomerPwaHeadLinks /><CustomerPwaUpdatePrompt /></>;
}
