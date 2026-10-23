"use client";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { extractPlatformTenantSlug } from "@/lib/platformDomains";
import RegisterServiceWorker from "./RegisterServiceWorker";
import DriverPwaStatus from "./DriverPwaStatus";
import DriverInstallPrompt from "./DriverInstallPrompt";
import DriverPwaDiagnostics from "./DriverPwaDiagnostics";
import CustomerPwaHeadLinks from "./CustomerPwaHeadLinks";
import CustomerPwaUpdatePrompt from "./CustomerPwaUpdatePrompt";
export default function AppPwaFeatures() {
  const path = usePathname(); const [tenant, setTenant] = useState<boolean | null>(null);
  useEffect(() => { setTenant(Boolean(extractPlatformTenantSlug(window.location.hostname))); }, []);
  if (tenant === null || ["/assine", "/onboarding", "/entrar"].includes(path ?? "") ||
    (path === "/" && process.env.NEXT_PUBLIC_SALES_SITE_ENABLED === "true" && !tenant)) return null;
  return <><CustomerPwaHeadLinks /><RegisterServiceWorker /><CustomerPwaUpdatePrompt /><DriverPwaStatus /><DriverInstallPrompt /><DriverPwaDiagnostics /></>;
}
