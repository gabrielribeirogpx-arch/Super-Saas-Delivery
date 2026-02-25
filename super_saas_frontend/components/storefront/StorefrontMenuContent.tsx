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
  const [activeCategoryId, setActiveCategoryId] = useState<string>("");
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
    if (!filteredUncategorizedItems.length) {
      return filteredCategories;
    }
    return [
      ...filteredCategories,
      {
        id: -1,
        name: "Sem categoria",
        emoji: "📦",
        sort_order: Number.MAX_SAFE_INTEGER,
        items: filteredUncategorizedItems,
      },
    ];
  }, [filteredCategories, filteredUncategorizedItems]);

  const visibleCategories = useMemo(() => {
    if (!activeCategoryId) {
      return categoriesForTabs;
    }
    return categoriesForTabs.filter((category) => String(category.id) === activeCategoryId);
  }, [activeCategoryId, categoriesForTabs]);

  const totalCents = useMemo(() => cart.reduce((total, entry) => total + entry.item.price_cents * entry.quantity, 0), [cart]);
  const cartItemsCount = useMemo(() => cart.reduce((total, entry) => total + entry.quantity, 0), [cart]);

  useEffect(() => {
    if (!categoriesForTabs.length) {
      setActiveCategoryId("");
      return;
    }

    const hasActiveCategory = categoriesForTabs.some((category) => String(category.id) === activeCategoryId);
    if (!hasActiveCategory) {
      setActiveCategoryId(String(categoriesForTabs[0].id));
    }
  }, [activeCategoryId, categoriesForTabs]);

  const handleSelectCategory = (categoryId: string) => {
    if (categoryId === "storefront-cart") {
      document.getElementById("storefront-cart")?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    setActiveCategoryId(categoryId);
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
    <div className="storefront-page min-h-screen" style={rootStyle}>
      <div className="store-card">
        <StorefrontHero
          store={{
            name: menu.tenant.name,
            subtitle: `@${menu.slug}${isPreview ? " • Prévia" : ""}`,
            logoUrl: theme.logoUrl,
            isOpen: Boolean(menu.tenant.is_open),
            estimatedTimeMin: menu.tenant.estimated_time_min ?? null,
          }}
          coverImageUrl={theme.coverImageUrl}
          bannerBlurEnabled={theme.bannerBlurEnabled}
          bannerBlurIntensity={theme.bannerBlurIntensity}
          bannerOverlayOpacity={theme.bannerOverlayOpacity}
        />

        <div className="store-content">
          <StorefrontCategoryTabs
            categories={categoriesForTabs}
            activeCategoryId={activeCategoryId}
            onSelectCategory={handleSelectCategory}
            cartCount={enableCart ? cartItemsCount : 0}
          />

          <main className="page">
        <label className="search-wrap block">
          <span aria-hidden className="search-ico">
            🔍
          </span>
          <input
            aria-label="Buscar no cardápio"
            placeholder="Buscar por nome ou descrição..."
            className="search-input"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>

        {menu.promo_code && (
          <section className="promo" id="promo-banner">
            <div>
              <div className="promo-label">🎉 Oferta especial</div>
              <h3 className="promo-title">Promoção de hoje</h3>
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

        <div id="categories-wrap">
          {visibleCategories.map((category) => (
            <section key={category.id} id={`sec-${category.id}`} className="scroll-mt-28 space-y-3">
              <div className="section-head">
                <h3 className="section-title">
                  <span>{category.emoji ?? "🍽️"}</span> {category.name}
                </h3>
                <span className="section-count">
                  {category.items.length} {category.items.length === 1 ? "item" : "itens"}
                </span>
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
              <span style={{ fontSize: 19 }}>🛒</span>
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
                <span className="cart-total-label">Total do pedido</span>
                <strong className="cart-total-value" id="cart-total">
                  R$ {formatPrice(totalCents)}
                </strong>
              </div>
              <button type="button" id="btn-finalizar" className="btn-finalizar" disabled={cart.length === 0}>
                Finalizar Pedido
              </button>
            </div>
          </section>
        )}
          </main>
        </div>
      </div>

      <footer>
        Powered by <a href="#">Super SaaS Delivery</a> &nbsp;·&nbsp; © 2025
      </footer>

      <div className={`toast ${toast ? "show" : ""}`} id="toast">
        {toast ? `🛒 ${toast}` : ""}
      </div>
    </div>
  );
}
