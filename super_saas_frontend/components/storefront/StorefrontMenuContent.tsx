"use client";

import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StorefrontCartBar } from "@/components/storefront/StorefrontCartBar";
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

export function StorefrontMenuContent({
  menu,
  isPreview = false,
  enableCart = true,
}: StorefrontMenuContentProps) {
  const [cart, setCart] = useState<CartItem[]>([]);
  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(null);

  const theme = getStoreTheme(menu.public_settings);

  const allCategories = useMemo<PublicMenuCategory[]>(() => {
    const isItemActive = (item: PublicMenuItem) => item.is_active !== false;

    const normalized = menu.categories
      .map((category) => ({
        ...category,
        items: category.items.filter(isItemActive),
      }))
      .filter((category) => category.items.length > 0);

    const itemsWithoutCategory = menu.items_without_category.filter(isItemActive);

    if (itemsWithoutCategory.length > 0) {
      normalized.push({
        id: -1,
        name: "Outros",
        sort_order: Number.MAX_SAFE_INTEGER,
        items: itemsWithoutCategory,
      });
    }

    return normalized;
  }, [menu.categories, menu.items_without_category]);

  const mostOrderedItems = useMemo(
    () => allCategories.flatMap((category) => category.items).filter((item) => item.is_popular),
    [allCategories]
  );

  useEffect(() => {
    if (!allCategories.length) {
      setActiveCategoryId(null);
      return;
    }

    setActiveCategoryId((currentCategoryId) => {
      if (
        currentCategoryId !== null
        && allCategories.some((category) => category.id === currentCategoryId)
      ) {
        return currentCategoryId;
      }

      return allCategories[0].id;
    });
  }, [allCategories]);

  const handleAddItem = (item: PublicMenuItem) => {
    if (!enableCart) {
      return;
    }

    setCart((prev) => {
      const existing = prev.find((entry) => entry.item.id === item.id);
      if (existing) {
        return prev.map((entry) =>
          entry.item.id === item.id
            ? { ...entry, quantity: entry.quantity + 1 }
            : entry
        );
      }
      return [...prev, { item, quantity: 1 }];
    });
  };

  const handleRemoveItem = (itemId: number) => {
    setCart((prev) =>
      prev
        .map((entry) =>
          entry.item.id === itemId
            ? { ...entry, quantity: entry.quantity - 1 }
            : entry
        )
        .filter((entry) => entry.quantity > 0)
    );
  };

  const totalCents = useMemo(
    () => cart.reduce((total, entry) => total + entry.item.price_cents * entry.quantity, 0),
    [cart]
  );
  const cartItemsCount = useMemo(
    () => cart.reduce((total, entry) => total + entry.quantity, 0),
    [cart]
  );

  const handleSelectCategory = (categoryId: number) => {
    setActiveCategoryId(categoryId);
    const section = document.getElementById(`category-${categoryId}`);
    section?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const openCart = () => {
    const section = document.getElementById("storefront-cart");
    section?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  return (
    <div className="min-h-screen bg-white pb-24">
      <StorefrontHero
        store={{
          name: menu.tenant.name,
          subtitle: `@${menu.slug}${isPreview ? " • Prévia" : ""}`,
          logoUrl: theme.logoUrl,
          isOpen: Boolean(menu.tenant.is_open),
        }}
        theme={theme}
        onCartClick={enableCart ? openCart : undefined}
      />

      <div className="pt-12">
        <StorefrontCartBar
          storeName={menu.tenant.name}
          cartItemsCount={enableCart ? cartItemsCount : 0}
          totalLabel={`R$ ${(totalCents / 100).toFixed(2)}`}
          buttonColor={theme.buttonColor}
          onCartClick={openCart}
          onMenuClick={() => handleSelectCategory(allCategories[0]?.id ?? 0)}
        />

        <StorefrontCategoryTabs
          categories={allCategories}
          activeCategoryId={activeCategoryId}
          onSelectCategory={handleSelectCategory}
          primaryColor={theme.primaryColor}
        />

        <main className="mx-auto w-full max-w-6xl space-y-8 px-4 py-6">
          {mostOrderedItems.length > 0 && (
            <section id="category-most-ordered" className="space-y-3 scroll-mt-28">
              <h2 className="text-lg font-semibold text-slate-900">Mais pedidos</h2>
              <div className="grid gap-4 md:grid-cols-2">
                {mostOrderedItems.map((item) => (
                  <StorefrontProductCard
                    key={`most-ordered-${item.id}`}
                    item={item}
                    buttonColor={theme.buttonColor}
                    onAdd={enableCart ? handleAddItem : undefined}
                  />
                ))}
              </div>
            </section>
          )}

          {allCategories.map((category) => (
            <section key={category.id} id={`category-${category.id}`} className="space-y-3 scroll-mt-28">
              <h2 className="text-lg font-semibold text-slate-900">{category.name}</h2>
              <div className="grid gap-4 md:grid-cols-2">
                {category.items.map((item) => (
                  <StorefrontProductCard
                    key={`${category.id}-${item.id}`}
                    item={item}
                    buttonColor={theme.buttonColor}
                    onAdd={enableCart ? handleAddItem : undefined}
                  />
                ))}
              </div>
            </section>
          ))}

          {enableCart && (
            <Card id="storefront-cart" className="rounded-2xl border-slate-200 shadow-sm">
              <CardContent className="space-y-3 p-4">
                <p className="text-sm font-semibold text-slate-900">Carrinho</p>
                {cart.length === 0 && (
                  <p className="text-xs text-slate-500">Nenhum item no carrinho.</p>
                )}
                {cart.length > 0 && (
                  <ul className="space-y-2 text-sm">
                    {cart.map((entry) => (
                      <li key={entry.item.id} className="flex items-center justify-between gap-2">
                        <span>
                          {entry.quantity}x {entry.item.name}
                        </span>
                        <div className="flex items-center gap-2">
                          <span>
                            R$ {((entry.item.price_cents * entry.quantity) / 100).toFixed(2)}
                          </span>
                          <Button variant="ghost" size="sm" onClick={() => handleRemoveItem(entry.item.id)}>
                            Remover
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="text-sm font-semibold text-slate-900">
                  Total: R$ {(totalCents / 100).toFixed(2)}
                </p>
              </CardContent>
            </Card>
          )}
        </main>
      </div>
    </div>
  );
}
