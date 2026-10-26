"use client";
import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { customerTenant } from "@/lib/customerAuth";
export default function CustomerPwaHeadLinks() {
  const pathname = usePathname();
  useEffect(() => {
    if (window.location.pathname.startsWith("/driver")) return;
    const add = (rel: string, href: string, attrs: Record<string, string> = {}) => {
      let el = document.head.querySelector(`link[data-customer-pwa="${rel}"]`) as HTMLLinkElement | null;
      if (!el) { el = document.createElement("link"); el.dataset.customerPwa = rel; document.head.appendChild(el); }
      el.rel = rel; el.href = href; Object.entries(attrs).forEach(([k, v]) => el!.setAttribute(k, v));
    };
    const tenant = customerTenant();
    if (!tenant) return;
    const query = `?tenant=${encodeURIComponent(tenant)}`;
    add("manifest", `/api/public/pwa/manifest${query}`);
    add("apple-touch-icon", `/api/public/pwa/icon/180${query}`, { sizes: "180x180" });
    return () => { document.head.querySelectorAll("link[data-customer-pwa]").forEach(link => link.remove()); };
  }, [pathname]);
  return null;
}
