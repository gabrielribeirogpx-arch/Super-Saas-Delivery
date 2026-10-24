"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  ChevronRight,
  Flame,
  LayoutGrid,
  LogOut,
  Menu,
  ShoppingBag,
  Truck,
  UtensilsCrossed,
  WifiOff,
  X,
} from "lucide-react";
import { authApi } from "@/lib/auth";
import { sidebarItems } from "@/components/sidebar";
import { useSession } from "@/hooks/use-session";
import { usePlanAccess } from "@/hooks/use-plan-access";
import { featureBlocked, routeFeature } from "@/lib/planAccess";
import { isDeliveryRole } from "@/lib/authorization";
import { canReviewBilling } from "@/lib/billingReviews";
import { cn } from "@/lib/utils";
import logo from "../public/fomizero-logo.svg";

const primaryItems = [
  { label: "Início", href: "/dashboard", icon: LayoutGrid },
  { label: "Pedidos", href: "/orders", icon: ShoppingBag },
  { label: "Cozinha", href: "/kds", icon: Flame },
  { label: "Cardápio", href: "/menu", icon: UtensilsCrossed },
];

export function Topbar() {
  const { data: session } = useSession();
  const access = usePlanAccess();
  const pathname = usePathname() ?? "";
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [offline, setOffline] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const deliveryOnly = isDeliveryRole(session?.role);
  const tenantId = session?.tenant_id ? String(session.tenant_id) : null;
  const resolveHref = (href: string) =>
    href.includes(":tenant_id")
      ? tenantId
        ? href.replace(":tenant_id", tenantId)
        : "/dashboard"
      : href;
  const items = sidebarItems.filter(
    (item) =>
      (!deliveryOnly || item.label === "Entregas") &&
      (item.label !== "Assinaturas" || canReviewBilling(session?.role)),
  );
  const tabs = deliveryOnly
    ? [
        {
          label: "Entregas",
          href: resolveHref("/admin/:tenant_id/delivery"),
          icon: Truck,
        },
      ]
    : primaryItems;
  const activeTab = tabs.find(
    (item) => pathname === item.href || pathname.startsWith(item.href + "/"),
  );
  const routeItem = items
    .flatMap(
      (item) =>
        item.children ??
        (item.href ? [{ ...item, href: resolveHref(item.href) }] : []),
    )
    .find(
      (item) => pathname === item.href || pathname.startsWith(item.href + "/"),
    );
  const title = activeTab?.label ?? routeItem?.label ?? "Minha loja";
  useEffect(() => {
    setIsOpen(false);
  }, [pathname]);

  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  useEffect(() => {
    const element = dialog.current;
    if (!element || !isOpen) return;
    const previousOverflow = document.body.style.overflow;
    const previousFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    element.showModal();
    document.body.style.overflow = "hidden";
    const desktop = window.matchMedia("(min-width: 1024px)");
    const closeOnDesktop = () => {
      if (desktop.matches) setIsOpen(false);
    };
    desktop.addEventListener("change", closeOnDesktop);
    return () => {
      element.close();
      document.body.style.overflow = previousOverflow;
      desktop.removeEventListener("change", closeOnDesktop);
      previousFocus?.focus({ preventScroll: true });
    };
  }, [isOpen]);

  const logout = async () => {
    setLoggingOut(true);
    setLogoutError(false);
    try {
      await authApi.logout();
      setIsOpen(false);
      router.push("/login");
    } catch {
      setLogoutError(true);
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <>
      <header className="admin-mobile-header sticky top-0 z-20 border-b border-slate-200/70 bg-white/95 px-4 backdrop-blur-xl lg:hidden">
        <div className="flex h-16 items-center justify-between gap-3">
          <Link
            href={tabs[0].href}
            aria-label="Fomizero — início"
            className="flex min-h-11 items-center"
          >
            <Image
              src={logo}
              alt="Fomizero"
              width={108}
              height={30}
              priority
              className="h-auto w-[108px]"
            />
          </Link>
          <span className="min-w-0 truncate text-sm font-semibold text-slate-600">
            {title}
          </span>
          <button
            type="button"
            onClick={() => setIsOpen(true)}
            aria-label="Abrir menu"
            aria-haspopup="dialog"
            aria-expanded={isOpen}
            aria-controls="admin-mobile-menu"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 text-slate-700"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>
        {offline && (
          <p
            role="status"
            className="flex items-center gap-2 pb-3 text-xs font-medium text-amber-800"
          >
            <WifiOff className="h-4 w-4 shrink-0" /> Sem conexão. Reconecte para
            atualizar sua loja.
          </p>
        )}
      </header>

      <nav
        aria-label="Navegação principal no celular"
        className="admin-bottom-nav fixed inset-x-0 bottom-0 z-30 border-t border-slate-200/80 bg-white/95 px-2 pt-2 backdrop-blur-xl lg:hidden"
      >
        <div className="mx-auto flex max-w-xl items-center justify-around gap-1">
          {tabs.map((item) => {
            const active = activeTab?.href === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-[52px] min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-2xl px-1 text-[11px] font-semibold",
                  active
                    ? "bg-brand-50 text-brand-700"
                    : "text-slate-500 hover:bg-slate-50",
                )}
              >
                <item.icon
                  className="h-5 w-5"
                  strokeWidth={active ? 2.4 : 1.8}
                />
                <span>{item.label}</span>
              </Link>
            );
          })}
          <button
            type="button"
            onClick={() => setIsOpen(true)}
            aria-haspopup="dialog"
            aria-expanded={isOpen}
            aria-controls="admin-mobile-menu"
            className={cn(
              "flex min-h-[52px] min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-2xl px-1 text-[11px] font-semibold",
              !activeTab || isOpen
                ? "bg-brand-50 text-brand-700"
                : "text-slate-500",
            )}
          >
            <LayoutGrid className="h-5 w-5" />
            <span>Mais</span>
          </button>
        </div>
      </nav>

      <dialog
        ref={dialog}
        id="admin-mobile-menu"
        aria-labelledby="admin-menu-title"
        onCancel={() => setIsOpen(false)}
        onClick={(event) => {
          if (event.target === event.currentTarget) setIsOpen(false);
        }}
        className="admin-menu-dialog fixed inset-0 m-0 h-dvh max-h-none w-full max-w-none bg-transparent p-0 text-slate-900 backdrop:bg-slate-950/40 backdrop:backdrop-blur-sm"
      >
        <div className="admin-menu-panel ml-auto flex h-full w-full max-w-lg flex-col bg-slate-50 shadow-2xl">
          <div className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-5 py-4">
            <div className="min-w-0">
              <Image
                src={logo}
                alt="Fomizero"
                width={132}
                height={35}
                className="h-auto w-[132px]"
              />
              <h2 id="admin-menu-title" className="sr-only">
                Navegação do restaurante
              </h2>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              aria-label="Fechar menu"
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <nav
            aria-label="Todas as áreas do restaurante"
            className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain p-4"
          >
            {[
              {
                label: "Operação",
                labels: [
                  "Dashboard",
                  "Pedidos",
                  "KDS",
                  "Entregas",
                  "Entregadores",
                ],
              },
              {
                label: "Gestão",
                labels: [
                  "Financeiro",
                  "Estoque",
                  "Relatórios",
                  "Cardápio",
                  "Prévia do Cardápio",
                  "Clientes",
                ],
              },
              { label: "Crescimento", labels: ["WhatsApp", "IA", "Marketing"] },
              {
                label: "Minha loja",
                labels: ["Minha Loja", "Usuários", "Auditoria", "Assinaturas"],
              },
            ].map((group) => {
              const entries = items.filter((item) =>
                group.labels.includes(item.label),
              );
              if (!entries.length) return null;
              return (
                <section key={group.label}>
                  <h3 className="mb-2 px-1 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500">
                    {group.label}
                  </h3>
                  <div className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200/80 bg-white">
                    {entries.map((item) =>
                      item.children ? (
                        <div key={item.label}>
                          <p className="px-4 pb-1 pt-3 text-xs font-semibold text-slate-500">
                            {item.label}
                          </p>
                          {item.children.map((child) => (
                            <MenuLink
                              key={child.href}
                              href={child.href}
                              label={child.label}
                              icon={child.icon ?? item.icon}
                              active={pathname === child.href}
                              blocked={featureBlocked(
                                access.data,
                                routeFeature(child.href),
                              )}
                              onClick={() => setIsOpen(false)}
                            />
                          ))}
                        </div>
                      ) : item.href ? (
                        <MenuLink
                          key={item.href}
                          href={resolveHref(item.href)}
                          label={
                            item.label === "Dashboard"
                              ? "Visão geral"
                              : item.label === "KDS"
                                ? "Cozinha"
                                : item.label
                          }
                          icon={item.icon}
                          active={pathname === resolveHref(item.href)}
                          blocked={featureBlocked(
                            access.data,
                            routeFeature(resolveHref(item.href)),
                          )}
                          onClick={() => setIsOpen(false)}
                        />
                      ) : null,
                    )}
                  </div>
                </section>
              );
            })}
          </nav>
          <div className="admin-menu-account shrink-0 border-t border-slate-200 bg-white px-5 pt-4">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-50 font-bold text-brand-700">
                {session?.name?.charAt(0).toUpperCase() || "F"}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold">
                  {session?.name || "Minha conta"}
                </p>
                <Link
                  href="/profile"
                  onClick={() => setIsOpen(false)}
                  className="inline-flex min-h-8 items-center text-xs text-slate-500 underline underline-offset-2"
                >
                  Meu perfil
                </Link>
              </div>
              <button
                type="button"
                disabled={loggingOut}
                onClick={logout}
                className="flex min-h-11 items-center gap-2 rounded-xl px-3 text-sm font-semibold text-slate-600 disabled:opacity-50"
              >
                <LogOut className="h-4 w-4" />
                {loggingOut ? "Saindo…" : "Sair"}
              </button>
            </div>
            {logoutError && (
              <p role="alert" className="mt-2 text-xs text-red-700">
                Não foi possível sair. Tente novamente.
              </p>
            )}
          </div>
        </div>
      </dialog>
    </>
  );
}

function MenuLink({
  href,
  label,
  icon: Icon,
  active,
  blocked,
  onClick,
}: {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  active: boolean;
  blocked: boolean;
  onClick: () => void;
}) {
  return (
    <Link
      href={href}
      prefetch={false}
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex min-h-14 items-center gap-3 px-4 py-3 text-sm font-medium",
        active
          ? "bg-brand-50 text-brand-700"
          : "text-slate-700 hover:bg-slate-50",
      )}
    >
      <span
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
          active ? "bg-white" : "bg-slate-50",
        )}
      >
        <Icon className="h-[18px] w-[18px]" />
      </span>
      <span className="min-w-0 flex-1">{label}</span>
      {blocked && (
        <span className="text-[10px] font-medium text-slate-500">
          Exige plano
        </span>
      )}
      <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" />
    </Link>
  );
}
