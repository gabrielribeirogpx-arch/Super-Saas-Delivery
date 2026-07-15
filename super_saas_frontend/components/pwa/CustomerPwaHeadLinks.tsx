"use client";
import { useEffect } from "react";
export default function CustomerPwaHeadLinks() {
  useEffect(() => {
    if (window.location.pathname.startsWith("/driver")) return;
    const add = (rel: string, href: string, attrs: Record<string, string> = {}) => {
      let el = document.head.querySelector(`link[data-customer-pwa="${rel}"]`) as HTMLLinkElement | null;
      if (!el) { el = document.createElement("link"); el.dataset.customerPwa = rel; document.head.appendChild(el); }
      el.rel = rel; el.href = href; Object.entries(attrs).forEach(([k, v]) => el!.setAttribute(k, v));
    };
    add("manifest", "/api/public/pwa/manifest");
    add("apple-touch-icon", "/api/public/pwa/icon/180", { sizes: "180x180" });
  }, []);
  return null;
}
