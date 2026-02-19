"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Card, CardContent } from "@/components/ui/card";
import { baseUrl } from "@/lib/api";

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

export default function StorefrontPage() {
  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(null);

  const menuQuery = useQuery({
    queryKey: ["public-menu"],
    queryFn: async () => {
      const response = await fetch(`${baseUrl}/public/menu`, {
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Falha ao carregar cardápio");
      }
      return (await response.json()) as PublicMenuResponse;
    },
  });

  if (menuQuery.isLoading) {
    return <p className="p-6 text-sm text-slate-500">Carregando cardápio...</p>;
  }

  if (menuQuery.isError || !menuQuery.data) {
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
    <main className="min-h-screen bg-slate-100 pb-28">
      <section className="relative overflow-hidden bg-gradient-to-br from-slate-950 via-slate-800 to-orange-700 px-5 py-14 text-white sm:px-8 lg:px-12 lg:py-20">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.24),transparent_45%)]" />
        <div className="relative mx-auto flex max-w-6xl flex-col gap-5">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-orange-100/80">
            Pedido online • Entrega rápida
          </p>
          <h1 className="max-w-3xl text-4xl font-black leading-tight sm:text-5xl lg:text-6xl">
            {menuQuery.data.tenant.name}
          </h1>
          <p className="max-w-2xl text-sm text-orange-50/90 sm:text-base">
            Escolha seus favoritos, personalize seu pedido e finalize em poucos toques.
          </p>
          <div>
            <button
              type="button"
              onClick={() => {
                const menuElement = document.getElementById("storefront-menu");
                if (!menuElement) return;
                menuElement.scrollIntoView({ behavior: "smooth", block: "start" });
              }}
              className="rounded-xl bg-white px-6 py-3 text-sm font-semibold text-slate-900 shadow-lg shadow-black/20 transition hover:-translate-y-0.5 hover:bg-orange-100"
            >
              Ver cardápio
            </button>
          </div>
        </div>
      </section>

      <section
        id="storefront-menu"
        className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur sm:px-8"
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
                    ? "border-orange-500 bg-orange-500 text-white shadow-md shadow-orange-200"
                    : "border-slate-200 bg-slate-50 text-slate-600 hover:border-orange-200 hover:text-slate-900"
                }`}
              >
                {category.name}
              </button>
            );
          })}
        </div>
      </section>

      <div className="mx-auto grid w-full max-w-6xl gap-6 px-4 py-6 lg:grid-cols-[220px_1fr] lg:px-8">
        <aside className="hidden h-fit rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:sticky lg:top-24 lg:block">
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
                    isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
                  }`}
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
                <h2 className="text-2xl font-bold text-slate-900">{category.name}</h2>
                <p className="text-xs text-slate-400">{category.items.length} itens</p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {category.items.map((item, index) => (
                  <Card
                    key={item.id}
                    className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md"
                  >
                    <div className="relative h-44 w-full bg-gradient-to-br from-slate-200 via-slate-100 to-white">
                      {item.image_url ? (
                        <img src={item.image_url} alt={item.name} className="h-full w-full object-cover" />
                      ) : (
                        <div className="flex h-full items-center justify-center text-xs font-semibold uppercase tracking-wider text-slate-500">
                          Imagem do produto
                        </div>
                      )}
                      {(item.is_popular || index === 0) && (
                        <span className="absolute left-3 top-3 rounded-full bg-slate-900 px-3 py-1 text-[11px] font-semibold text-white">
                          🔥 Mais pedido
                        </span>
                      )}
                    </div>
                    <CardContent className="space-y-3 p-4">
                      <p className="text-lg font-bold text-slate-900">{item.name}</p>
                      <p className="line-clamp-2 text-sm text-slate-500">
                        {item.description || "Delicioso item preparado com ingredientes selecionados."}
                      </p>
                      <div className="flex items-center justify-between">
                        <p className="text-xl font-extrabold text-slate-900">{formatPrice(item.price_cents)}</p>
                        <button
                          type="button"
                          className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white transition hover:bg-orange-600"
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

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white/95 p-4 backdrop-blur lg:hidden">
        <button
          type="button"
          className="flex w-full items-center justify-between rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-slate-400/30"
        >
          <span>🛒 Ver carrinho</span>
          <span>{selectedItemsCount} itens</span>
        </button>
      </div>
    </main>
  );
}
