"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Card, CardContent } from "@/components/ui/card";
import { apiFetch, baseUrl } from "@/lib/api";
import { useStoreAppearance } from "@/hooks/useStoreAppearance";

interface PublicMenuItem {
  id: number;
  name: string;
  description?: string | null;
  price_cents: number;
  image_url?: string | null;
  is_popular?: boolean;
}

interface PublicMenuCategory {
  id: number;
  name: string;
  items: PublicMenuItem[];
}

interface PublicMenuResponse {
  tenant: { name: string };
  categories: PublicMenuCategory[];
}

interface TenantResponse {
  slug: string;
}

export default function StorefrontPage() {
  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(null);
  const { appearance } = useStoreAppearance();

  const tenantQuery = useQuery({
    queryKey: ["storefront-tenant"],
    queryFn: () => apiFetch("/api/admin/tenant", { credentials: "include" }).then((response) => {
      if (!response.ok) {
        throw new Error("Falha ao carregar tenant");
      }
      return response.json() as Promise<TenantResponse>;
    }),
  });

  const menuQuery = useQuery({
    queryKey: ["public-menu", tenantQuery.data?.slug],
    enabled: Boolean(tenantQuery.data?.slug),
    queryFn: async () => {
      const response = await apiFetch(`${baseUrl}/public/menu?slug=${encodeURIComponent(tenantQuery.data!.slug)}`, {
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Falha ao carregar cardápio");
      }
      return (await response.json()) as PublicMenuResponse;
    },
  });

  if (tenantQuery.isLoading || menuQuery.isLoading) {
    return <p className="p-6 text-sm text-slate-500">Carregando cardápio...</p>;
  }

  if (tenantQuery.isError || !tenantQuery.data?.slug || menuQuery.isError || !menuQuery.data) {
    return <p className="p-6 text-sm text-red-600">Não foi possível carregar o cardápio.</p>;
  }

  const categories = menuQuery.data.categories;
  const selectedCategoryId = activeCategoryId ?? categories[0]?.id ?? null;
  const selectedItemsCount = useMemo(
    () =>
      categories.find((category) => category.id === selectedCategoryId)?.items.length ??
      categories.reduce((acc, category) => acc + category.items.length, 0),
    [categories, selectedCategoryId],
  );

  const scrollToCategory = (categoryId: number) => {
    setActiveCategoryId(categoryId);
    const section = document.getElementById(`category-${categoryId}`);
    if (!section) return;
    section.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const formatPrice = (priceCents: number) =>
    new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(priceCents / 100);

  return (
    <main
      className="min-h-screen bg-slate-950 pb-28 text-slate-100"
      style={{ fontFamily: "var(--font-family), sans-serif" }}
    >
      <section
        className="relative overflow-hidden border-b border-white/10 px-5 py-16 sm:px-8 lg:px-12 lg:py-20"
        style={{
          backgroundImage: appearance.hero_image_url
            ? `linear-gradient(rgba(2, 6, 23, 0.45), rgba(2, 6, 23, 0.75)), url(${appearance.hero_image_url})`
            : "radial-gradient(circle at top, #1e293b 0%, #020617 55%, #020617 100%)",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="pointer-events-none absolute -left-32 top-10 h-64 w-64 rounded-full bg-orange-500/20 blur-3xl" />
        <div className="pointer-events-none absolute right-4 top-2 h-56 w-56 rounded-full bg-cyan-400/20 blur-3xl" />
        <div className="relative mx-auto grid max-w-6xl gap-8 lg:grid-cols-[1.4fr_1fr] lg:items-end">
          <div className="space-y-5">
            {appearance.logo_url && (
              <img
                src={appearance.logo_url}
                alt={`Logo ${menuQuery.data.tenant.name}`}
                className="h-16 w-16 rounded-full border-2 border-white/60 object-cover"
              />
            )}
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-orange-200/90">
              Pedido online • Entrega rápida
            </p>
            <h1 className="max-w-3xl text-4xl font-black leading-tight text-white sm:text-5xl lg:text-6xl">
              {menuQuery.data.tenant.name}
            </h1>
            <p className="max-w-2xl text-sm text-slate-200 sm:text-base">
              Uma vitrine moderna para explorar sabores, descobrir os mais pedidos e montar seu carrinho em segundos.
            </p>
            <div>
              <button
                type="button"
                onClick={() => {
                  const menuElement = document.getElementById("storefront-menu");
                  if (!menuElement) return;
                  menuElement.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
                className="px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-black/30 transition hover:-translate-y-0.5"
                style={{
                  background: "var(--primary-color)",
                  borderRadius: "var(--button-radius)",
                }}
              >
                Explorar cardápio
              </button>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
            <div className="rounded-2xl border border-white/15 bg-white/5 p-4 backdrop-blur">
              <p className="text-xs uppercase tracking-wider text-slate-300">Categorias</p>
              <p className="mt-2 text-2xl font-bold text-white">{categories.length}</p>
            </div>
            <div className="rounded-2xl border border-white/15 bg-white/5 p-4 backdrop-blur">
              <p className="text-xs uppercase tracking-wider text-slate-300">Itens disponíveis</p>
              <p className="mt-2 text-2xl font-bold text-white">{selectedItemsCount}</p>
            </div>
            <div className="rounded-2xl border border-white/15 bg-white/5 p-4 backdrop-blur">
              <p className="text-xs uppercase tracking-wider text-slate-300">Entrega média</p>
              <p className="mt-2 text-2xl font-bold text-white">30 min</p>
            </div>
          </div>
        </div>
      </section>

      <section
        id="storefront-menu"
        className="sticky top-0 z-20 border-b border-white/10 bg-slate-950/90 px-4 py-3 backdrop-blur sm:px-8"
      >
        <div className="mx-auto flex max-w-6xl gap-2 overflow-x-auto pb-1">
          {categories.map((category) => {
            const isActive = selectedCategoryId === category.id;
            return (
              <button
                key={category.id}
                type="button"
                onClick={() => scrollToCategory(category.id)}
                className={`shrink-0 rounded-xl border px-4 py-2 text-sm font-semibold transition ${
                  isActive
                    ? "border-orange-400 text-white shadow-md shadow-orange-700/40"
                    : "border-slate-700 bg-slate-900 text-slate-300 hover:border-orange-400/60 hover:text-white"
                }`}
                style={isActive ? { background: "var(--primary-color)", borderRadius: "var(--button-radius)" } : { borderRadius: "var(--button-radius)" }}
              >
                {category.name}
              </button>
            );
          })}
        </div>
      </section>

      <div className="mx-auto grid w-full max-w-6xl gap-6 px-4 py-8 lg:grid-cols-[220px_1fr] lg:px-8">
        <aside className="hidden h-fit rounded-2xl border border-white/10 bg-slate-900 p-4 shadow-xl shadow-black/20 lg:sticky lg:top-24 lg:block">
          <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-400">Categorias</p>
          <div className="space-y-2">
            {categories.map((category) => {
              const isActive = selectedCategoryId === category.id;
              return (
                <button
                  key={`sidebar-${category.id}`}
                  type="button"
                  onClick={() => scrollToCategory(category.id)}
                  className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-sm transition ${
                    isActive ? "text-white" : "text-slate-300 hover:bg-slate-800"
                  }`}
                  style={isActive ? { background: "var(--primary-color)", borderRadius: "var(--button-radius)" } : { borderRadius: "var(--button-radius)" }}
                >
                  <span>{category.name}</span>
                  <span className="text-xs opacity-80">{category.items.length}</span>
                </button>
              );
            })}
          </div>
        </aside>

        <div className="space-y-8">
          {categories.map((category) => (
            <section key={category.id} id={`category-${category.id}`} className="space-y-4 scroll-mt-24">
              <div className="flex items-end justify-between">
                <h2 className="text-2xl font-bold text-white">{category.name}</h2>
                <p className="text-xs text-slate-400">{category.items.length} itens</p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {category.items.map((item, index) => (
                  <Card
                    key={item.id}
                    className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900 shadow-lg shadow-black/20 transition duration-200 hover:-translate-y-0.5 hover:shadow-orange-900/20"
                    style={{ borderRadius: "var(--button-radius)" }}
                  >
                    <div className="relative h-44 w-full bg-gradient-to-br from-slate-800 via-slate-700 to-slate-900">
                      {item.image_url ? (
                        <img src={item.image_url} alt={item.name} className="h-full w-full object-cover" />
                      ) : (
                        <div className="flex h-full items-center justify-center text-xs font-semibold uppercase tracking-wider text-slate-300">
                          Imagem do produto
                        </div>
                      )}
                      {(item.is_popular || index === 0) && (
                        <span
                          className="absolute left-3 top-3 rounded-full px-3 py-1 text-[11px] font-semibold text-white"
                          style={{ background: "var(--primary-color)", borderRadius: "var(--button-radius)" }}
                        >
                          🔥 Mais pedido
                        </span>
                      )}
                    </div>
                    <CardContent className="space-y-3 p-4">
                      <p className="text-lg font-bold text-white">{item.name}</p>
                      <p className="line-clamp-2 text-sm text-slate-400">
                        {item.description || "Delicioso item preparado com ingredientes selecionados."}
                      </p>
                      <div className="flex items-center justify-between">
                        <p className="text-xl font-extrabold" style={{ color: "var(--primary-color)" }}>
                          {formatPrice(item.price_cents)}
                        </p>
                        <button
                          type="button"
                          className="px-4 py-2 text-xs font-semibold text-white transition"
                          style={{
                            background: "var(--primary-color)",
                            borderRadius: "var(--button-radius)",
                          }}
                        >
                          Adicionar
                        </button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-white/10 bg-slate-950/95 p-4 backdrop-blur lg:hidden">
        <button
          type="button"
          className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-orange-900/30"
          style={{ background: "var(--primary-color)", borderRadius: "var(--button-radius)" }}
        >
          <span>🛒 Ver carrinho</span>
          <span>{selectedItemsCount} itens</span>
        </button>
      </div>
    </main>
  );
}
