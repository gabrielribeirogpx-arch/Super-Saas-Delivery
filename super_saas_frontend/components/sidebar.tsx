"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  Boxes,
  Eye,
  Flame,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Palette,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Store,
  Users,
  UtensilsCrossed,
  Wallet,
  ChevronDown,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { authApi } from "@/lib/auth";
import { cn } from "@/lib/utils";

export interface SidebarItem {
  label: string;
  href?: string;
  icon: React.ComponentType<{ className?: string }>;
  children?: Array<{
    label: string;
    href: string;
    icon?: React.ComponentType<{ className?: string }>;
  }>;
}

export const sidebarItems: SidebarItem[] = [
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
  {
    label: "Minha Loja",
    icon: Store,
    children: [
      { label: "Informações", href: "/minha-loja" },
      { label: "Aparência", href: "/admin/appearance", icon: Palette },
    ],
  },
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

          if (item.children) {
            const hasActiveChild = item.children.some((child) => pathname === child.href);
            return (
              <div key={item.label} className="space-y-1">
                <div
                  className={cn(
                    "flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-[background] duration-200 ease-in-out",
                    hasActiveChild
                      ? "rounded-[8px] bg-black/[0.04] text-slate-900"
                      : "text-slate-600"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </div>
                  <ChevronDown className="h-4 w-4" />
                </div>
                <div className="ml-7 space-y-1 border-l border-slate-200 pl-3">
                  {item.children.map((child) => {
                    const ChildIcon = child.icon;
                    const active = pathname === child.href;
                    return (
                      <Link
                        key={child.href}
                        href={child.href}
                        className={cn(
                          "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-[background] duration-200 ease-in-out",
                          active
                            ? "rounded-[8px] bg-black/[0.04] text-slate-900"
                            : "text-slate-600 hover:bg-black/[0.03]"
                        )}
                      >
                        {ChildIcon ? <ChildIcon className="h-4 w-4" /> : null}
                        {child.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          }

          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href ?? "#"}
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
