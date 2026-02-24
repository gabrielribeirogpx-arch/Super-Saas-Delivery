"use client";

import { CSSProperties, useEffect, useMemo, useState } from "react";

import { StorefrontCategoryTabs } from "@/components/storefront/StorefrontCategoryTabs";
import { StorefrontHero } from "@/components/storefront/StorefrontHero";
import { StorefrontProductCard } from "@/components/storefront/StorefrontProductCard";
import { CartItem, PublicMenuCategory, PublicMenuItem, PublicMenuResponse } from "@/components/storefront/types";
import { getStoreTheme } from "@/lib/storeTheme";

interface StorefrontMenuContentProps {
  menu: PublicMenuResponse;
  isPreview?: boolean;
  enableCart?: boolean;
}

const THEME_KEY = "theme";

type StorefrontTheme = "white" | "blue";

const formatBRL = (value: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value / 100);

export function StorefrontMenuContent({ menu, isPreview = false, enableCart = true }: StorefrontMenuContentProps) {
  const [cart, setCart] = useState<CartItem[]>([]);
  const [activeCategoryId, setActiveCategoryId] = useState<string>("top-picks");
  const [search, setSearch] = useState("");
  const [themeMode, setThemeMode] = useState<StorefrontTheme>("white");
  const [toast, setToast] = useState<string | null>(null);
  const [justAddedId, setJustAddedId] = useState<number | null>(null);

  const theme = getStoreTheme(menu.public_settings);

  useEffect(() => {
    const stored = window.localStorage.getItem(THEME_KEY);
    const nextTheme = stored === "blue" ? "blue" : "white";
    setThemeMode(nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", themeMode);
    window.localStorage.setItem(THEME_KEY, themeMode);
  }, [themeMode]);

  useEffect(() => {
    const ids = ["sec-top-picks", ...menu.categories.map((category) => `sec-${category.id}`)];
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);

        if (visible[0]?.target.id === "sec-top-picks") {
          setActiveCategoryId("top-picks");
          return;
        }

        if (visible[0]?.target.id.startsWith("sec-")) {
          setActiveCategoryId(visible[0].target.id.replace("sec-", ""));
        }
      },
      { rootMargin: "-40% 0px -45% 0px", threshold: [0.2, 0.45, 0.7] }
    );

    ids.forEach((id) => {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    });

    return () => observer.disconnect();
  }, [menu.categories]);

  const normalizedCategories = useMemo<PublicMenuCategory[]>(() => {
    const isItemActive = (item: PublicMenuItem) => item.is_active !== false;
    const query = search.trim().toLowerCase();

    const normalized = menu.categories
      .map((category) => ({
        ...category,
        items: category.items.filter((item) => {
          if (!isItemActive(item)) return false;
          if (!query) return true;
          const haystack = `${item.name} ${item.description ?? ""}`.toLowerCase();
          return haystack.includes(query);
        }),
      }))
      .filter((category) => category.items.length > 0);

    const itemsWithoutCategory = menu.items_without_category.filter((item) => {
      if (!isItemActive(item)) return false;
      if (!query) return true;
      const haystack = `${item.name} ${item.description ?? ""}`.toLowerCase();
      return haystack.includes(query);
    });

    if (itemsWithoutCategory.length > 0) {
      normalized.push({ id: -1, name: "Outros", sort_order: Number.MAX_SAFE_INTEGER, items: itemsWithoutCategory });
    }

    return normalized;
  }, [menu.categories, menu.items_without_category, search]);

  const mostOrderedItems = useMemo(
    () => normalizedCategories.flatMap((category) => category.items).filter((item) => item.is_popular),
    [normalizedCategories]
  );

  const totalCents = useMemo(() => cart.reduce((total, entry) => total + entry.item.price_cents * entry.quantity, 0), [cart]);
  const cartItemsCount = useMemo(() => cart.reduce((total, entry) => total + entry.quantity, 0), [cart]);

  const handleSelectCategory = (categoryId: string) => {
    setActiveCategoryId(categoryId);
    const anchor = categoryId === "top-picks" ? "sec-top-picks" : `sec-${categoryId}`;
    document.getElementById(anchor)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleAddItem = (item: PublicMenuItem) => {
    if (!enableCart) return;

    setCart((prev) => {
      const existing = prev.find((entry) => entry.item.id === item.id);
      if (existing) {
        return prev.map((entry) => (entry.item.id === item.id ? { ...entry, quantity: entry.quantity + 1 } : entry));
      }
      return [...prev, { item, quantity: 1 }];
    });

    setJustAddedId(item.id);
    setToast(`🛒 ${item.name} adicionado!`);
    window.setTimeout(() => setJustAddedId(null), 1200);
    window.setTimeout(() => setToast(null), 2200);
  };

  const customAccent = /^#([0-9A-Fa-f]{3}){1,2}$/.test(theme.primaryColor) ? theme.primaryColor : null;
  const rootStyle = (customAccent ? {"--accent": customAccent, "--accent-h": customAccent} : undefined) as CSSProperties | undefined;

  return (
    <div className="storefront-page min-h-screen pb-24" style={rootStyle}>
      <StorefrontHero
        store={{ name: menu.tenant.name, subtitle: `@${menu.slug}${isPreview ? " • Prévia" : ""}`, logoUrl: theme.logoUrl, isOpen: Boolean(menu.tenant.is_open) }}
        theme={theme}
      />

      <div className="storefront-sticky-nav sticky top-0 z-[90]">
        <StorefrontCategoryTabs
          categories={normalizedCategories}
          activeCategoryId={activeCategoryId}
          onSelectCategory={handleSelectCategory}
          primaryColor={theme.primaryColor}
          cartCount={enableCart ? cartItemsCount : 0}
        />
      </div>

      <main className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6">
        <label className="search-shell flex items-center gap-2 rounded-[50px] border px-4 py-3">
          <span aria-hidden>🔍</span>
          <input
            aria-label="Buscar no cardápio"
            placeholder="Buscar por nome ou descrição"
            className="w-full bg-transparent text-sm outline-none"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>

        {menu.promo_code && (
          <section className="promo-banner relative overflow-hidden rounded-2xl border p-4">
            <span className="pointer-events-none absolute right-3 top-0 text-6xl opacity-10">🎁</span>
            <p className="text-sm">Cupom ativo</p>
            <p className="mt-1 text-2xl font-bold tracking-[4px]">{menu.promo_code}</p>
            {menu.promo_description && <p className="mt-2 text-sm">{menu.promo_description}</p>}
          </section>
        )}

        {mostOrderedItems.length > 0 && (
          <section id="sec-top-picks" className="space-y-3 scroll-mt-28">
            <h2 className="font-display text-2xl">⭐ Mais pedidos</h2>
            <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(min(100%,270px),1fr))]">
              {mostOrderedItems.map((item) => (
                <StorefrontProductCard key={`top-${item.id}`} item={item} onAdd={handleAddItem} justAdded={justAddedId === item.id} topPick />
              ))}
            </div>
          </section>
        )}

        {normalizedCategories.map((category) => (
          <section key={category.id} id={`sec-${category.id}`} className="space-y-3 scroll-mt-28">
            <div className="flex items-center justify-between">
              <h3 className="font-display text-xl">🍽️ {category.name}</h3>
              <span className="text-sm opacity-80">{category.items.length} itens</span>
            </div>
            <div className="space-y-3">
              {category.items.map((item) => (
                <StorefrontProductCard key={`${category.id}-${item.id}`} item={item} onAdd={handleAddItem} justAdded={justAddedId === item.id} />
              ))}
            </div>
          </section>
        ))}

        {enableCart && (
          <section id="storefront-cart" className="rounded-2xl border p-4">
            <h4 className="text-sm font-semibold">Carrinho</h4>
            {cart.length === 0 && <p className="mt-2 text-sm opacity-70">Nenhum item no carrinho.</p>}
            {cart.length > 0 && (
              <ul className="mt-3 space-y-2 text-sm">
                {cart.map((entry) => (
                  <li key={entry.item.id} className="flex items-center justify-between">
                    <span>{entry.quantity}x {entry.item.name}</span>
                    <span>{formatBRL(entry.item.price_cents * entry.quantity)}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 font-semibold">Total: {formatBRL(totalCents)}</p>
          </section>
        )}
      </main>

      <div className="theme-toggle fixed bottom-5 right-5 z-[999] inline-flex gap-2 rounded-[50px] border p-1">
        <button type="button" className={`theme-btn ${themeMode === "white" ? "active" : ""}`} onClick={() => setThemeMode("white")}>☀ Clean White</button>
        <button type="button" className={`theme-btn ${themeMode === "blue" ? "active" : ""}`} onClick={() => setThemeMode("blue")}>🌙 Blue Dark</button>
      </div>

      {toast && <div className="storefront-toast fixed bottom-[76px] left-1/2 z-[999] -translate-x-1/2 rounded-full px-4 py-2 text-sm">{toast}</div>}

      <footer className="mx-auto mt-8 w-full max-w-6xl border-t px-4 py-6 text-sm opacity-80">
        Powered by <a href="https://example.com" className="underline">Super SaaS Delivery</a>
      </footer>
    </div>
  );
}
