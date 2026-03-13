"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { label: "Home", path: "" },
  { label: "Orders", path: "/orders" },
  { label: "Discounts", path: "/discounts" },
  { label: "Profile", path: "/profile" },
];

export function CustomerBottomNav({ slug }: { slug: string }) {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t bg-white md:hidden">
      <div className="grid grid-cols-4">
        {tabs.map((tab) => {
          const href = `/loja/${slug}${tab.path}`;
          const active = pathname === href;
          return (
            <Link key={tab.label} href={href} className={`p-3 text-center text-xs ${active ? "font-semibold text-black" : "text-slate-500"}`}>
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
