"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { resolveStorefrontTenant } from "@/lib/storefrontApi";

export function CustomerBottomNav({ slug }: { slug?: string }) {
  const pathname = usePathname();
  const [cartCount, setCartCount] = useState(0);
  const tenant = useMemo(() => slug || resolveStorefrontTenant() || "", [slug]);
  useEffect(() => {
    const read = () => {
      try {
        const raw = localStorage.getItem(`mobile-storefront-cart:${tenant}`);
        const items = raw ? JSON.parse(raw) : [];
        setCartCount(Array.isArray(items) ? items.reduce((s, i) => s + Number(i.quantity || 0), 0) : 0);
      } catch { setCartCount(0); }
    };
    read();
    window.addEventListener("storage", read);
    const id = window.setInterval(read, 1000);
    return () => { window.removeEventListener("storage", read); window.clearInterval(id); };
  }, [tenant]);
  if (pathname.startsWith("/driver")) return null;
  const tabs = [
    { label: "Início", href: "/" },
    { label: "Pedidos", href: "/account/orders" },
    { label: "Carrinho", href: "#cart" },
    { label: "Conta", href: "/account" },
  ];
  return (
    <nav
      className="fixed inset-x-0 bottom-0 border-t bg-white md:hidden"
      style={{
        height: "calc(var(--customer-bottom-nav-height) + var(--customer-safe-bottom))",
        paddingBottom: "var(--customer-safe-bottom)",
        zIndex: "var(--customer-z-bottom-nav)",
      }}
    >
      <div className="grid h-[var(--customer-bottom-nav-height)] grid-cols-4">
        {tabs.map((tab) => {
          const active = tab.href !== "#cart" && (pathname === tab.href || (tab.href !== "/" && pathname.startsWith(tab.href)));
          const content = <span>{tab.label}{tab.label === "Carrinho" && cartCount > 0 ? <b className="ml-1 rounded-full bg-slate-950 px-1.5 py-0.5 text-[10px] text-white">{cartCount}</b> : null}</span>;
          if (tab.href === "#cart") return <button key={tab.label} className="min-h-11 p-3 text-center text-xs text-slate-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-slate-950" onClick={() => window.dispatchEvent(new CustomEvent("storefront-open-cart"))}>{content}</button>;
          return <Link key={tab.label} href={tab.href} className={`min-h-11 p-3 text-center text-xs focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-slate-950 ${active ? "font-semibold text-black" : "text-slate-500"}`}>{content}</Link>;
        })}
      </div>
    </nav>
  );
}
