"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { label: "Início", href: "/" },
  { label: "Pedidos", href: "/my-orders" },
  { label: "Carrinho", href: "/cart" },
];

export function CustomerBottomNav({ slug: _slug }: { slug?: string }) {
  const pathname = usePathname();
  if (pathname.startsWith("/driver")) return null;

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t bg-white md:hidden">
      <div className="grid grid-cols-3">
        {tabs.map((tab) => {
          const active = pathname === tab.href || (tab.href !== "/" && pathname.startsWith(tab.href));
          return (
            <Link key={tab.label} href={tab.href} className={`p-3 text-center text-xs ${active ? "font-semibold text-black" : "text-slate-500"}`}>
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
