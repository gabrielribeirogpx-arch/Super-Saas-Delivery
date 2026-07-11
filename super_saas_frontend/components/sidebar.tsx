"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import {
  BarChart3,
  Boxes,
  Eye,
  Flame,
  LayoutDashboard,
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
  Bike,
  Megaphone,
} from "lucide-react";

import serviceDeliveryLogo from "../public/service-delivery-logo.svg";

import { UserIdentity } from "@/components/UserIdentity";
import { useSession } from "@/hooks/use-session";
import { authApi } from "@/lib/auth";
import { cn } from "@/lib/utils";

export interface SidebarItem {
  label: string;
  href?: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
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
  { label: "Entregas", href: "/admin/:tenant_id/delivery", icon: Bike },
  { label: "Entregadores", href: "/admin/:tenant_id/delivery-users", icon: Bike },
  { label: "Financeiro", href: "/finance", icon: Wallet },
  { label: "Estoque", href: "/inventory", icon: Boxes },
  { label: "Relatórios", href: "/reports", icon: BarChart3 },
  { label: "Cardápio", href: "/menu", icon: UtensilsCrossed },
  { label: "Prévia do Cardápio", href: "/storefront-preview", icon: Eye, badge: "Novo" },
  { label: "WhatsApp", href: "/whatsapp", icon: MessageCircle },
  { label: "IA", href: "/ai", icon: Sparkles },
  {
    label: "Marketing",
    icon: Megaphone,
    children: [
      { label: "Fidelidade", href: "/marketing/loyalty" },
      { label: "Cupons", href: "/marketing/coupons" },
      { label: "Recompensas", href: "/marketing/rewards" },
    ],
  },
  {
    label: "Minha Loja",
    icon: Store,
    children: [
      { label: "Informações", href: "/minha-loja" },
      { label: "Aparência", href: "/admin/appearance", icon: Palette },
    ],
  },
  { label: "Clientes", href: "/customers", icon: Users },
  { label: "Usuários", href: "/users", icon: Users },
  { label: "Auditoria", href: "/audit", icon: ShieldCheck },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session } = useSession();
  const [openMenus, setOpenMenus] = useState({
    marketing: false,
    store: false,
  });
  const tenantIdFromPath = pathname?.match(/^\/admin\/([^/]+)\//)?.[1] ?? null;
  const tenantId = tenantIdFromPath ?? (session?.tenant_id ? String(session.tenant_id) : null);
  const normalizedPathname = pathname ?? "";

  const isDashboardActive = normalizedPathname === "/dashboard";
  const isDeliveryUsersActive =
    normalizedPathname.startsWith("/delivery-users") ||
    /^\/admin\/[^/]+\/delivery-users(?:\/|$)/.test(normalizedPathname);
  const isDeliveryActive =
    (normalizedPathname.startsWith("/delivery") ||
      /^\/admin\/[^/]+\/delivery(?:\/|$)/.test(normalizedPathname)) &&
    !isDeliveryUsersActive;

  const resolveHref = (href?: string) => {
    if (!href) return "#";
    if (!href.includes(":tenant_id")) return href;
    if (!tenantId) return "/dashboard";
    return href.replace(":tenant_id", tenantId);
  };

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } finally {
      router.push("/login");
    }
  };

  const toggleMenu = (menu: "marketing" | "store") => {
    setOpenMenus((prev) => ({
      ...prev,
      [menu]: !prev[menu],
    }));
  };

  return (
    <aside className="hidden h-screen w-64 flex-col border-r border-slate-200 bg-white px-4 py-6 md:flex">
      <Link
        href="/dashboard"
        aria-label="Dashboard"
        className="mb-6 flex cursor-pointer justify-center py-2"
      >
        <Image
          src={serviceDeliveryLogo}
          alt="Service Delivery"
          width={200}
          height={61}
          className="h-auto w-full max-w-[177px] md:max-w-[197px]"
          priority
        />
      </Link>
      <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
        {sidebarItems.map((item) => {
          const Icon = item.icon;

          if (item.children) {
            const hasActiveChild = item.children.some((child) => pathname === child.href);
            const menuKey = item.label === "Marketing" ? "marketing" : "store";
            const isOpen = openMenus[menuKey];

            return (
              <div key={item.label} className="space-y-1">
                <button
                  type="button"
                  onClick={() => toggleMenu(menuKey)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150 ease-in-out hover:bg-gray-100",
                    hasActiveChild
                      ? "rounded-[8px] bg-black/[0.04] text-slate-900"
                      : "text-slate-600"
                  )}
                  aria-expanded={isOpen}
                  aria-label={`Alternar ${item.label}`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </div>
                  <ChevronDown
                    className={cn(
                      "h-4 w-4 transition-transform duration-200",
                      isOpen && "rotate-180"
                    )}
                  />
                </button>
                {isOpen && (
                  <div className="ml-7 space-y-1 border-l border-slate-200 pl-3 transition-all duration-200 ease-in-out">
                    {item.children.map((child) => {
                      const ChildIcon = child.icon;
                      const active = pathname === child.href;
                      return (
                        <Link
                          key={child.href}
                          href={child.href}
                          className={cn(
                            "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150 ease-in-out hover:bg-gray-100",
                            active
                              ? "rounded-[8px] bg-black/[0.04] text-slate-900"
                              : "text-slate-600"
                          )}
                        >
                          {ChildIcon ? <ChildIcon className="h-4 w-4" /> : null}
                          {child.label}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          }

          const itemHref = resolveHref(item.href);

          let active = normalizedPathname === itemHref;

          if (item.label === "Dashboard") {
            active = isDashboardActive;
          }

          if (item.label === "Entregadores") {
            active = isDeliveryUsersActive;
          }

          if (item.label === "Entregas") {
            active = isDeliveryActive;
          }

          return (
            <Link
              key={item.href}
              href={itemHref}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150 ease-in-out hover:bg-gray-100",
                active
                  ? "rounded-[8px] bg-black/[0.04] text-slate-900"
                  : "text-slate-600"
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
              {item.badge ? (
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                  {item.badge}
                </span>
              ) : null}
            </Link>
          );
        })}
      </nav>
      {session ? (
        <div className="mt-auto border-t border-slate-200 pt-4">
          <UserIdentity user={session} onLogout={handleLogout} dropdownSide="top" />
        </div>
      ) : null}
    </aside>
  );
}
