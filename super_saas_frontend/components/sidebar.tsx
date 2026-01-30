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
  LogOut,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { authApi } from "@/lib/auth";
import { cn } from "@/lib/utils";

const items = [
  { label: "Dashboard", href: "dashboard", icon: LayoutDashboard },
  { label: "Pedidos", href: "orders", icon: ShoppingBag },
  { label: "KDS", href: "kds", icon: Flame },
  { label: "Financeiro", href: "finance", icon: Wallet },
  { label: "Estoque", href: "inventory", icon: Boxes },
  { label: "Relatórios", href: "reports", icon: BarChart3 },
  { label: "WhatsApp", href: "whatsapp", icon: MessageCircle },
  { label: "IA", href: "ai", icon: Sparkles },
  { label: "Usuários", href: "users", icon: Users },
  { label: "Auditoria", href: "audit", icon: ShieldCheck },
];

export function Sidebar({ tenantId }: { tenantId: string }) {
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
    <aside className="flex h-full w-64 flex-col border-r border-slate-200 bg-white px-4 py-6">
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase text-slate-400">
          Super SaaS Delivery
        </p>
        <h2 className="text-lg font-semibold text-slate-900">Painel Admin</h2>
      </div>
      <nav className="flex-1 space-y-1">
        {items.map((item) => {
          const Icon = item.icon;
          const href = `/t/${tenantId}/${item.href}`;
          const active = pathname === href;
          return (
            <Link
              key={item.href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
                active
                  ? "bg-brand-50 text-brand-700"
                  : "text-slate-600 hover:bg-slate-100"
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
