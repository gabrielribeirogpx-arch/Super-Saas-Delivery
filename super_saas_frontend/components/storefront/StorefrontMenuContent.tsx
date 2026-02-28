"use client";

import { CSSProperties, useEffect, useMemo, useState } from "react";

import { StorefrontCategoryTabs } from "@/components/storefront/StorefrontCategoryTabs";
import { StorefrontHero } from "@/components/storefront/StorefrontHero";
import { formatPrice, StorefrontProductCard } from "@/components/storefront/StorefrontProductCard";
import { CartItem, PublicMenuCategory, PublicMenuItem, PublicMenuResponse } from "@/components/storefront/types";
import { getStoreTheme } from "@/lib/storeTheme";

interface StorefrontMenuContentProps {
  menu: PublicMenuResponse;
  enableCart?: boolean;
}

export function StorefrontMenuContent({ menu, enableCart = true }: StorefrontMenuContentProps) {
  const [cart, setCart] = useState<CartItem[]>([]);
  const [activeCategoryId, setActiveCategoryId] = useState<string>("");
  const [search, setSearch] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [justAddedId, setJustAddedId] = useState<number | null>(null);
  const [configuratorItem, setConfiguratorItem] = useState<PublicMenuItem | null>(null);
  const [selectedModifiers, setSelectedModifiers] = useState<Record<number, number[]>>({});
  const isPreview = typeof window !== "undefined" && window.location.pathname.includes("storefront-preview");

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

  const totalCents = useMemo(
    () =>
      cart.reduce((total, entry) => {
        const modifiersTotal = (entry.selected_modifiers ?? []).reduce((acc, mod) => acc + mod.price_cents, 0);
        return total + (entry.item.price_cents + modifiersTotal) * entry.quantity;
      }, 0),
    [cart]
  );
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
    window.requestAnimationFrame(() => {
      document.getElementById(`sec-${categoryId}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  const openConfigurator = (item: PublicMenuItem) => {
    const defaults: Record<number, number[]> = {};
    (item.modifier_groups ?? []).forEach((group) => {
      defaults[group.id] = group.options.filter((option) => option.is_active && option.is_default).map((option) => option.id);
    });
    setSelectedModifiers(defaults);
    setConfiguratorItem(item);
  };

  const closeConfigurator = () => {
    setConfiguratorItem(null);
  };

  const addConfiguredItemToCart = (item: PublicMenuItem, modifiers: Array<{ group_id: number; option_id: number; name: string; price_cents: number }>) => {
    setCart((prev) => {
      const signature = JSON.stringify(modifiers.map((mod) => `${mod.group_id}:${mod.option_id}`).sort());
      const existing = prev.find(
        (entry) =>
          entry.item.id === item.id &&
          JSON.stringify((entry.selected_modifiers ?? []).map((mod) => `${mod.group_id}:${mod.option_id}`).sort()) === signature
      );
      if (existing) {
        return prev.map((entry) =>
          entry.item.id === item.id &&
          JSON.stringify((entry.selected_modifiers ?? []).map((mod) => `${mod.group_id}:${mod.option_id}`).sort()) === signature
            ? { ...entry, quantity: entry.quantity + 1 }
            : entry
        );
      }
      return [...prev, { item, quantity: 1, selected_modifiers: modifiers }];
    });

    setJustAddedId(item.id);
    setToast(`${item.name} adicionado!`);
    window.setTimeout(() => setJustAddedId(null), 1200);
    window.setTimeout(() => setToast(null), 2200);
    closeConfigurator();
  };

  const activeModifierGroups = useMemo(
    () => (configuratorItem?.modifier_groups ?? []).map((group) => ({ ...group, options: group.options.filter((option) => option.is_active) })),
    [configuratorItem]
  );

  const validationByGroup = useMemo(() => {
    const result: Record<number, string> = {};
    activeModifierGroups.forEach((group) => {
      if (!group.required) return;
      const selectedCount = (selectedModifiers[group.id] ?? []).length;
      const min = Math.max(group.min_selection, 1);
      if (selectedCount < min) {
        result[group.id] = `Selecione ao menos ${min} opção${min > 1 ? "ões" : ""}.`;
      }
    });
    return result;
  }, [activeModifierGroups, selectedModifiers]);

  function calculateTotal() {
    if (!configuratorItem) return 0;
    const modifiersTotal = activeModifierGroups.reduce((acc, group) => {
      const selectedIds = selectedModifiers[group.id] ?? [];
      return (
        acc +
        group.options.reduce((groupAcc, option) => {
          if (!selectedIds.includes(option.id)) return groupAcc;
          return groupAcc + Math.round((Number(option.price_delta) || 0) * 100);
        }, 0)
      );
    }, 0);
    return configuratorItem.price_cents + modifiersTotal;
  }

  const configuratorTotalCents = calculateTotal();
  const isConfiguratorValid = Object.keys(validationByGroup).length === 0;

  const selectedModifierPayload = useMemo(() => {
    if (!configuratorItem) return [] as Array<{ group_id: number; option_id: number; name: string; price_cents: number }>;
    return activeModifierGroups.flatMap((group) =>
      group.options
        .filter((option) => (selectedModifiers[group.id] ?? []).includes(option.id))
        .map((option) => ({
          group_id: group.id,
          option_id: option.id,
          name: option.name,
          price_cents: Math.round((Number(option.price_delta) || 0) * 100),
        }))
    );
  }, [activeModifierGroups, configuratorItem, selectedModifiers]);

  return (
    <div className="storefront-page min-h-screen" style={rootStyle}>
      <div className="store-card">
        <StorefrontHero
          store={{
            name: menu.tenant.name,
            subtitle: `@${menu.slug}${isPreview ? " • Prévia" : ""}`,
            logoUrl: theme.logoUrl,
            isOpen: menu.tenant.manual_open_status ?? true,
            waitTime: menu.tenant.estimated_prep_time ?? null,
            fee: "Grátis",
            rating: "4.9",
            totalReviews: "312",
          }}
          coverImageUrl={theme.coverImageUrl}
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
                      <StorefrontProductCard key={`${category.id}-${item.id}`} item={item} onAdd={enableCart ? openConfigurator : undefined} justAdded={justAddedId === item.id} />
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
                      {cart.map((entry) => {
                        const modifiersLabel = (entry.selected_modifiers ?? []).map((modifier) => modifier.name).join(", ");
                        const modifierTotal = (entry.selected_modifiers ?? []).reduce((acc, modifier) => acc + modifier.price_cents, 0);
                        return (
                          <div className="cart-row" key={`${entry.item.id}-${modifiersLabel || "simple"}`}>
                            <div className="cart-row-qty">{entry.quantity}x</div>
                            <div className="cart-row-name">
                              {entry.item.name}
                              {modifiersLabel ? <small className="cart-row-modifiers">{modifiersLabel}</small> : null}
                            </div>
                            <div className="cart-row-price">R$ {formatPrice((entry.item.price_cents + modifierTotal) * entry.quantity)}</div>
                          </div>
                        );
                      })}
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

      {enableCart && (
        <div
          id="productConfigurator"
          className={`product-configurator ${configuratorItem ? "open" : ""}`}
          aria-hidden={!configuratorItem}
          onClick={(event) => {
            if (event.target === event.currentTarget) closeConfigurator();
          }}
        >
          {configuratorItem && (
            <div className="product-configurator-sheet">
              <header className="product-configurator-header">
                <div>
                  <h3>{configuratorItem.name}</h3>
                  <p>Configure seus adicionais</p>
                </div>
                <button type="button" className="product-configurator-close" onClick={closeConfigurator} aria-label="Fechar configurador">
                  ✕
                </button>
              </header>

              <div className="product-configurator-body">
                {activeModifierGroups.map((group) => {
                  const current = selectedModifiers[group.id] || [];
                  const inputType = group.max_selection === 1 ? "radio" : "checkbox";
                  return (
                    <section key={group.id} className="configurator-group">
                      <div className="configurator-group-head">
                        <h4>{group.name}</h4>
                        {group.required ? <span className="configurator-badge-required">Obrigatório</span> : null}
                      </div>
                      {group.description ? <p className="configurator-group-description">{group.description}</p> : null}
                      <div className="configurator-options">
                        {group.options.map((option) => {
                          const checked = current.includes(option.id);
                          return (
                            <label key={option.id} className="configurator-option-row">
                              <input
                                type={inputType}
                                name={`group-${group.id}`}
                                checked={checked}
                                onChange={() => {
                                  setSelectedModifiers((prev) => {
                                    const existing = prev[group.id] || [];
                                    if (group.max_selection === 1) {
                                      return { ...prev, [group.id]: [option.id] };
                                    }
                                    if (existing.includes(option.id)) {
                                      return { ...prev, [group.id]: existing.filter((id) => id !== option.id) };
                                    }
                                    if (existing.length >= group.max_selection) return prev;
                                    return { ...prev, [group.id]: [...existing, option.id] };
                                  });
                                }}
                              />
                              <span>{option.name}</span>
                              <strong>+ R$ {(Number(option.price_delta) || 0).toFixed(2).replace(".", ",")}</strong>
                            </label>
                          );
                        })}
                      </div>
                      {validationByGroup[group.id] ? <p className="configurator-validation-message">{validationByGroup[group.id]}</p> : null}
                    </section>
                  );
                })}
              </div>

              <footer className="product-configurator-footer">
                <div className="configurator-total-wrap">
                  <small>Total</small>
                  <strong>R$ {formatPrice(configuratorTotalCents)}</strong>
                </div>
                <button
                  type="button"
                  className="configurator-confirm-button"
                  disabled={!isConfiguratorValid}
                  onClick={() => {
                    if (!isConfiguratorValid) return;

                    const payload = {
                      product_id: configuratorItem.id,
                      quantity: 1,
                      selected_modifiers: selectedModifierPayload.map((modifier) => ({
                        group_id: modifier.group_id,
                        option_id: modifier.option_id,
                      })),
                    };
                    void payload;

                    addConfiguredItemToCart(configuratorItem, selectedModifierPayload);
                  }}
                >
                  Adicionar ao carrinho
                </button>
              </footer>
            </div>
          )}
        </div>
      )}

      <footer>
        Powered by <a href="#">Super SaaS Delivery</a> &nbsp;·&nbsp; © 2025
      </footer>

      <div className={`toast ${toast ? "show" : ""}`} id="toast">
        {toast ? `🛒 ${toast}` : ""}
      </div>
    </div>
  );
}
