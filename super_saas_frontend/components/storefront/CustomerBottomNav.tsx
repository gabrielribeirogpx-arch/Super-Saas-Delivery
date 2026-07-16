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
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t bg-white md:hidden">
      <div className="grid grid-cols-4">
        {tabs.map((tab) => {
          const active = tab.href !== "#cart" && (pathname === tab.href || (tab.href !== "/" && pathname.startsWith(tab.href)));
          const content = <span>{tab.label}{tab.label === "Carrinho" && cartCount > 0 ? <b className="ml-1 rounded-full bg-slate-950 px-1.5 py-0.5 text-[10px] text-white">{cartCount}</b> : null}</span>;
          if (tab.href === "#cart") return <button key={tab.label} className="p-3 text-center text-xs text-slate-500" onClick={() => window.dispatchEvent(new CustomEvent("storefront-open-cart"))}>{content}</button>;
          return <Link key={tab.label} href={tab.href} className={`p-3 text-center text-xs ${active ? "font-semibold text-black" : "text-slate-500"}`}>{content}</Link>;
        })}
      </div>
    </nav>
  );
}
