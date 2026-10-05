"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Home, Receipt, ShoppingCart, User } from "lucide-react";
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
    { label: "Início", href: "/", Icon: Home },
    { label: "Pedidos", href: "/account/orders", Icon: Receipt },
    { label: "Carrinho", href: "#cart", Icon: ShoppingCart },
    { label: "Conta", href: "/account", Icon: User },
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
      <div className="grid h-[var(--customer-bottom-nav-height)] grid-cols-[repeat(4,minmax(0,1fr))]">
        {tabs.map((tab) => {
          const active = tab.href !== "#cart" && (pathname === tab.href || (tab.href !== "/" && pathname.startsWith(tab.href)));
          const content = (
            <>
              <span className="relative">
                <tab.Icon aria-hidden="true" className="h-[17px] w-[17px]" />
                {tab.label === "Carrinho" && cartCount > 0 ? (
                  <b className="absolute -right-2.5 -top-2 min-w-4 rounded-full bg-slate-950 px-1 text-center text-[9px] font-semibold leading-4 text-white">
                    {cartCount}
                  </b>
                ) : null}
              </span>
              <span className="leading-none">{tab.label}</span>
            </>
          );
          const itemClassName = `flex min-h-11 min-w-0 flex-col items-center justify-center gap-1 px-1 py-2 text-center text-xs focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-slate-950 ${active ? "font-semibold text-black" : "text-slate-500"}`;
          if (tab.href === "#cart") return (
            <button key={tab.label} className={itemClassName} onClick={() => window.dispatchEvent(new CustomEvent("storefront-open-cart"))}>
              {content}
            </button>
          );
          return <Link key={tab.label} href={tab.href} className={itemClassName}>{content}</Link>;
        })}
      </div>
    </nav>
  );
}
