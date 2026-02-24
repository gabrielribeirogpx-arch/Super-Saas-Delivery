"use client";

import { CSSProperties, useEffect, useMemo, useState } from "react";

import { StorefrontCategoryTabs } from "@/components/storefront/StorefrontCategoryTabs";
import { StorefrontHero } from "@/components/storefront/StorefrontHero";
import { formatPrice, StorefrontProductCard } from "@/components/storefront/StorefrontProductCard";
import { CartItem, PublicMenuCategory, PublicMenuItem, PublicMenuResponse } from "@/components/storefront/types";
import { getStoreTheme } from "@/lib/storeTheme";

interface StorefrontMenuContentProps {
  menu: PublicMenuResponse;
  isPreview?: boolean;
  enableCart?: boolean;
}

export function StorefrontMenuContent({ menu, isPreview = false, enableCart = true }: StorefrontMenuContentProps) {
  const [cart, setCart] = useState<CartItem[]>([]);
  const [activeCategoryId, setActiveCategoryId] = useState<string>("top");
  const [search, setSearch] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [justAddedId, setJustAddedId] = useState<number | null>(null);

  const theme = getStoreTheme(menu.public_settings);

  const customAccent = /^#([0-9A-Fa-f]{3}){1,2}$/.test(theme.primaryColor) ? theme.primaryColor : null;
  const rootStyle = (customAccent
    ? {
        "--accent": customAccent,
        "--accent-d": customAccent,
      }
    : undefined) as CSSProperties | undefined;

  const filteredCategories = useMemo<PublicMenuCategory[]>(() => {
    const query = search.trim().toLowerCase();
    return menu.categories
      .map((category) => ({
        ...category,
        items: category.items.filter((item) => {
          if (item.is_active === false) return false;
          if (!query) return true;
          return `${item.name} ${item.description ?? ""}`.toLowerCase().includes(query);
        }),
      }))
      .filter((category) => category.items.length > 0);
  }, [menu.categories, search]);

  const filteredUncategorizedItems = useMemo(() => {
    const query = search.trim().toLowerCase();
    return menu.items_without_category.filter((item) => {
      if (item.is_active === false) return false;
      if (!query) return true;
      return `${item.name} ${item.description ?? ""}`.toLowerCase().includes(query);
    });
  }, [menu.items_without_category, search]);

  const categoriesForTabs = useMemo<PublicMenuCategory[]>(() => {
    const baseCategories = filteredCategories;
    if (!filteredUncategorizedItems.length) {
      return baseCategories;
    }
    return [
      ...baseCategories,
      {
        id: -1,
        name: "Sem categoria",
        emoji: "📦",
        sort_order: Number.MAX_SAFE_INTEGER,
        items: filteredUncategorizedItems,
      },
    ];
  }, [filteredCategories, filteredUncategorizedItems]);

  const mostOrderedItems = useMemo(() => categoriesForTabs.flatMap((category) => category.items).filter((item) => item.is_popular), [categoriesForTabs]);

  const totalCents = useMemo(() => cart.reduce((total, entry) => total + entry.item.price_cents * entry.quantity, 0), [cart]);
  const cartItemsCount = useMemo(() => cart.reduce((total, entry) => total + entry.quantity, 0), [cart]);

  useEffect(() => {
    const spy = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const id = entry.target.id;
          if (id === "sec-top") {
            setActiveCategoryId("top");
            return;
          }
          if (id.startsWith("sec-")) {
            setActiveCategoryId(id.replace("sec-", ""));
          }
        });
      },
      { threshold: 0.25, rootMargin: "-56px 0px -48% 0px" }
    );

    const timer = window.setTimeout(() => {
      document.querySelectorAll("section[id^='sec-']").forEach((section) => spy.observe(section));
    }, 300);

    return () => {
      window.clearTimeout(timer);
      spy.disconnect();
    };
  }, [categoriesForTabs, mostOrderedItems.length]);

  useEffect(() => {
    if (mostOrderedItems.length > 0) return;
    if (categoriesForTabs.length > 0) {
      setActiveCategoryId(String(categoriesForTabs[0].id));
      return;
    }
    setActiveCategoryId("top");
  }, [categoriesForTabs, mostOrderedItems.length]);

  const handleSelectCategory = (categoryId: string) => {
    setActiveCategoryId(categoryId);
    const anchor = categoryId === "top" ? "sec-top" : categoryId === "storefront-cart" ? "storefront-cart" : `sec-${categoryId}`;
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
    setToast(`${item.name} adicionado!`);
    window.setTimeout(() => setJustAddedId(null), 1200);
    window.setTimeout(() => setToast(null), 2200);
  };

  return (
    <div className="storefront-page min-h-screen pb-24" style={rootStyle}>
      <StorefrontHero
        store={{
          name: menu.tenant.name,
          subtitle: `@${menu.slug}${isPreview ? " · Prévia" : ""}`,
          logoUrl: theme.logoUrl,
          isOpen: Boolean(menu.tenant.is_open),
          delivery: "~30 min",
          fee: "Grátis",
          rating: "4.9",
          totalReviews: "312",
        }}
        coverImageUrl={theme.coverImageUrl}
      />

      <StorefrontCategoryTabs
        categories={categoriesForTabs}
        activeCategoryId={activeCategoryId}
        onSelectCategory={handleSelectCategory}
        cartCount={enableCart ? cartItemsCount : 0}
        showTopTab={mostOrderedItems.length > 0}
      />

      <main className="mx-auto w-full max-w-[1000px] px-4 py-6">
        <label className="search-wrap block">
          <span aria-hidden className="search-ico">
            🔍
          </span>
          <input aria-label="Buscar no cardápio" placeholder="Buscar por nome ou descrição" className="search-input" value={search} onChange={(event) => setSearch(event.target.value)} />
        </label>

        {menu.promo_code && (
          <section className="promo" id="promo-banner">
            <div>
              <div className="promo-label">Cupom especial</div>
              <h3 className="promo-title">Aproveite hoje no pedido</h3>
              <p className="promo-desc" id="promo-desc">
                {menu.promo_description ?? ""}
              </p>
            </div>
            <div className="promo-code-box">
              <small>Use o código</small>
              <strong id="promo-code">{menu.promo_code}</strong>
            </div>
          </section>
        )}

        {mostOrderedItems.length > 0 && (
          <section id="sec-top" className="scroll-mt-28 space-y-3">
            <div className="section-head">
              <h2 className="section-title">⭐ Mais pedidos</h2>
              <span className="section-count" id="top-count">
                {mostOrderedItems.length} itens
              </span>
            </div>
            <div className="featured-grid" id="featured-grid">
              {mostOrderedItems.map((item) => (
                <StorefrontProductCard key={`top-${item.id}`} item={item} onAdd={handleAddItem} justAdded={justAddedId === item.id} topPick />
              ))}
            </div>
          </section>
        )}

        <div id="categories-wrap">
          {categoriesForTabs.map((category) => (
            <section key={category.id} id={`sec-${category.id}`} className="scroll-mt-28 space-y-3">
              <div className="section-head">
                <h3 className="section-title">
                  <span>{category.emoji ?? "🍽️"}</span> {category.name}
                </h3>
                <span className="section-count">{category.items.length} itens</span>
              </div>
              <div className="menu-list">
                {category.items.map((item) => (
                  <StorefrontProductCard key={`${category.id}-${item.id}`} item={item} onAdd={handleAddItem} justAdded={justAddedId === item.id} />
                ))}
              </div>
            </section>
          ))}
        </div>

        {enableCart && (
          <section id="storefront-cart" className="cart-panel">
            <div className="cart-header">
              <span>🛒</span>
              <div className="cart-header-title">Seu carrinho</div>
            </div>
            <div id="cart-body">
              {cart.length === 0 ? (
                <div className="cart-empty">
                  <div className="cart-empty-ico">🛒</div>
                  <p>Nenhum item no carrinho.</p>
                  <small>Adicione itens do cardápio acima</small>
                </div>
              ) : (
                <div className="cart-items-list">
                  {cart.map((entry) => (
                    <div className="cart-row" key={entry.item.id}>
                      <div className="cart-row-qty">{entry.quantity}x</div>
                      <div className="cart-row-name">{entry.item.name}</div>
                      <div className="cart-row-price">R$ {formatPrice(entry.item.price_cents * entry.quantity)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="cart-footer">
              <div className="cart-total">
                <span className="cart-total-label">Total</span>
                <strong className="cart-total-value" id="cart-total">
                  R$ {formatPrice(totalCents)}
                </strong>
              </div>
              <button type="button" id="btn-finalizar" className="btn-finalizar" disabled={cart.length === 0}>
                Finalizar pedido
              </button>
            </div>
          </section>
        )}
      </main>

      <div className={`toast ${toast ? "show" : ""}`} id="toast">
        {toast ? `🛒 ${toast}` : ""}
      </div>
    </div>
  );
}
