"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { href: "/driver/dashboard", label: "Dashboard" },
  { href: "/driver/orders", label: "Pedidos" },
  { href: "/driver/delivery", label: "Entrega" },
  { href: "/driver/map", label: "Mapa" },
];

export default function DriverLayout({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col bg-slate-50 p-4 pb-20">
      <header className="mb-4">
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
      </header>
      <section className="flex-1">{children}</section>

      <nav className="fixed bottom-0 left-0 right-0 border-t bg-white p-2">
        <ul className="mx-auto grid max-w-md grid-cols-4 gap-1">
          {tabs.map((tab) => (
            <li key={tab.href}>
              <Link
                href={tab.href}
                className={`block rounded px-2 py-2 text-center text-xs ${
                  pathname === tab.href ? "bg-slate-900 text-white" : "text-slate-700"
                }`}
              >
                {tab.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </main>
  );
}
