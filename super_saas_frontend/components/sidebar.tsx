"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  ShoppingBag,
  Flame,
  Wallet,
  Boxes,
  BarChart3,
  MessageCircle,
  Sparkles,
  Users,
  ShieldCheck,
  UtensilsCrossed,
  Store,
  Eye,
  Palette,
  LogOut,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { authApi } from "@/lib/auth";
import { cn } from "@/lib/utils";

export const sidebarItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Pedidos", href: "/orders", icon: ShoppingBag },
  { label: "KDS", href: "/kds", icon: Flame },
  { label: "Financeiro", href: "/finance", icon: Wallet },
  { label: "Estoque", href: "/inventory", icon: Boxes },
  { label: "Relatórios", href: "/reports", icon: BarChart3 },
  { label: "Cardápio", href: "/menu", icon: UtensilsCrossed },
  { label: "Prévia do Cardápio", href: "/storefront-preview", icon: Eye },
  { label: "WhatsApp", href: "/whatsapp", icon: MessageCircle },
  { label: "IA", href: "/ai", icon: Sparkles },
  { label: "Minha Loja", href: "/settings", icon: Store },
  { label: "Appearance", href: "/appearance", icon: Palette },
  { label: "Usuários", href: "/users", icon: Users },
  { label: "Auditoria", href: "/audit", icon: ShieldCheck },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } finally {
      router.push("/login");
    }
  };

  return (
    <aside className="hidden h-full w-64 flex-col border-r border-slate-200 bg-white px-4 py-6 md:flex">
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase text-slate-400">Super SaaS Delivery</p>
        <h2 className="text-lg font-semibold text-slate-900">Painel Admin</h2>
      </div>
      <nav className="flex-1 space-y-1">
        {sidebarItems.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-[background] duration-200 ease-in-out",
                active
                  ? "rounded-[8px] bg-black/[0.04] text-slate-900"
                  : "text-slate-600 hover:bg-black/[0.03]"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <Button variant="outline" className="mt-4" onClick={handleLogout}>
        <LogOut className="mr-2 h-4 w-4" />
        Sair
      </Button>
    </aside>
  );
}
