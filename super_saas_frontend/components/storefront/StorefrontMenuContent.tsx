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

const formatBRL = (value: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value / 100);

export function StorefrontMenuContent({ menu, isPreview = false, enableCart = true }: StorefrontMenuContentProps) {
  const [cart, setCart] = useState<CartItem[]>([]);
  const [activeCategoryId, setActiveCategoryId] = useState<string>("top-picks");
  const [search, setSearch] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [justAddedId, setJustAddedId] = useState<number | null>(null);

  const theme = getStoreTheme(menu.public_settings);

  const customAccent = /^#([0-9A-Fa-f]{3}){1,2}$/.test(theme.primaryColor) ? theme.primaryColor : null;
  const rootStyle = (customAccent
    ? {
        "--accent": customAccent,
        "--accent-dark": customAccent,
        "--accent-soft": `${customAccent}1A`,
      }
    : undefined) as CSSProperties | undefined;

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
      normalized.push({ id: -1, name: "Outros", emoji: "🍽️", sort_order: Number.MAX_SAFE_INTEGER, items: itemsWithoutCategory });
    }

    return normalized;
  }, [menu.categories, menu.items_without_category, search]);

  const mostOrderedItems = useMemo(
    () => normalizedCategories.flatMap((category) => category.items).filter((item) => item.is_popular),
    [normalizedCategories]
  );

  const totalCents = useMemo(() => cart.reduce((total, entry) => total + entry.item.price_cents * entry.quantity, 0), [cart]);
  const cartItemsCount = useMemo(() => cart.reduce((total, entry) => total + entry.quantity, 0), [cart]);

  useEffect(() => {
    const ids = ["sec-top-picks", ...normalizedCategories.map((category) => `sec-${category.id}`), "storefront-cart"];
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        const currentId = visible[0]?.target.id;
        if (!currentId) return;

        if (currentId === "sec-top-picks") {
          setActiveCategoryId("top-picks");
          return;
        }

        if (currentId.startsWith("sec-")) {
          setActiveCategoryId(currentId.replace("sec-", ""));
          return;
        }

        if (currentId === "storefront-cart") {
          setActiveCategoryId("storefront-cart");
        }
      },
      { threshold: 0.25, rootMargin: "-56px 0px -50% 0px" }
    );

    ids.forEach((id) => {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    });

    return () => observer.disconnect();
  }, [normalizedCategories]);

  const handleSelectCategory = (categoryId: string) => {
    setActiveCategoryId(categoryId);
    const anchor = categoryId === "top-picks" ? "sec-top-picks" : categoryId === "storefront-cart" ? "storefront-cart" : `sec-${categoryId}`;
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

  const hasAnyResult = normalizedCategories.some((category) => category.items.length > 0);

  return (
    <div className="storefront-page min-h-screen pb-24" style={rootStyle}>
      <StorefrontHero
        store={{
          name: menu.tenant.name,
          subtitle: `@${menu.slug}${isPreview ? " · Prévia" : ""}`,
          logoUrl: theme.logoUrl,
          isOpen: Boolean(menu.tenant.is_open),
        }}
        theme={theme}
      />

      <StorefrontCategoryTabs categories={normalizedCategories} activeCategoryId={activeCategoryId} onSelectCategory={handleSelectCategory} cartCount={enableCart ? cartItemsCount : 0} />

      <main className="mx-auto w-full max-w-6xl px-4 py-6">
        <label className="search-wrap block">
          <span aria-hidden className="search-icon">🔍</span>
          <input
            aria-label="Buscar no cardápio"
            placeholder="Buscar por nome ou descrição"
            className="search-input"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>

        {menu.promo_code && (
          <section className="promo-banner">
            <div>
              <h3 className="promo-title">Oferta especial</h3>
              {menu.promo_description && <p className="promo-desc">{menu.promo_description}</p>}
            </div>
            <div className="promo-code">{menu.promo_code}</div>
          </section>
        )}

        {mostOrderedItems.length > 0 && (
          <section id="sec-top-picks" className="scroll-mt-28 space-y-3">
            <div className="section-head">
              <h2 className="section-title">⭐ Mais pedidos</h2>
              <span className="section-count">{mostOrderedItems.length} itens</span>
            </div>
            <div className="featured-grid">
              {mostOrderedItems.map((item) => (
                <StorefrontProductCard key={`top-${item.id}`} item={item} onAdd={handleAddItem} justAdded={justAddedId === item.id} topPick />
              ))}
            </div>
          </section>
        )}

        {normalizedCategories.map((category) => (
          <section key={category.id} id={`sec-${category.id}`} className="scroll-mt-28 space-y-3">
            <div className="section-head">
              <h3 className="section-title">
                {category.emoji ?? "🍽️"} {category.name}
              </h3>
              <span className="section-count">{category.items.length} itens</span>
            </div>
            <div className="space-y-3">
              {category.items.map((item) => (
                <StorefrontProductCard key={`${category.id}-${item.id}`} item={item} onAdd={handleAddItem} justAdded={justAddedId === item.id} />
              ))}
            </div>
          </section>
        ))}

        {search.trim().length > 0 && !hasAnyResult && (
          <section className="rounded-2xl border border-dashed border-[var(--border-strong)] bg-[var(--surface)] px-5 py-10 text-center">
            <p className="text-sm text-[var(--muted)]">Nenhum item encontrado para "{search}".</p>
          </section>
        )}

        {enableCart && (
          <section id="storefront-cart" className="mt-8 rounded-2xl border bg-[var(--surface)] p-4">
            <h4 className="font-display text-[18px]">Carrinho</h4>
            {cart.length === 0 && <p className="mt-2 text-sm text-[var(--muted)]">🛒 Nenhum item no carrinho.</p>}
            {cart.length > 0 && (
              <ul className="mt-3 space-y-2 text-sm">
                {cart.map((entry) => (
                  <li key={entry.item.id} className="flex items-center justify-between">
                    <span>
                      {entry.quantity}x {entry.item.name}
                    </span>
                    <span>{formatBRL(entry.item.price_cents * entry.quantity)}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 font-semibold">Total: {formatBRL(totalCents)}</p>
            <button type="button" className="mt-3 w-full rounded-xl bg-[var(--accent)] px-4 py-3 text-sm font-semibold text-white">
              Finalizar Pedido
            </button>
          </section>
        )}
      </main>

      {toast && <div className={`toast ${toast ? "show" : ""}`}>{toast}</div>}

      <footer className="mx-auto mt-8 w-full max-w-6xl px-4">
        Powered by <a href="https://example.com">Super SaaS Delivery</a>
      </footer>
    </div>
  );
}
