"use client";

import { CSSProperties, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StorefrontCartBar } from "@/components/storefront/StorefrontCartBar";
import { StorefrontCategoryTabs } from "@/components/storefront/StorefrontCategoryTabs";
import { StorefrontHero } from "@/components/storefront/StorefrontHero";
import { StorefrontProductCard } from "@/components/storefront/StorefrontProductCard";
import { CartItem, PublicMenuCategory, PublicMenuItem, PublicMenuResponse } from "@/components/storefront/types";
import { api } from "@/lib/api";

interface StoreThemeResponse {
  primary_color: string | null;
  secondary_color: string | null;
  logo_url: string | null;
  cover_url: string | null;
  slogan: string | null;
  show_logo_on_cover: boolean;
}

interface StorefrontMenuContentProps {
  menu: PublicMenuResponse;
  isPreview?: boolean;
  enableCart?: boolean;
}

const defaultTheme = {
  primaryColor: "#2563EB",
  secondaryColor: "#2563EB",
  buttonBg: "#2563EB",
  buttonText: "#FFFFFF",
};

export function StorefrontMenuContent({
  menu,
  isPreview = false,
  enableCart = true,
}: StorefrontMenuContentProps) {
  const [cart, setCart] = useState<CartItem[]>([]);
  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(
    menu.categories[0]?.id ?? null
  );

  const themeQuery = useQuery({
    queryKey: ["store-theme"],
    queryFn: () => api.get<StoreThemeResponse>("/api/store/theme"),
    retry: 0,
  });

  const resolvedTheme = {
    primaryColor: themeQuery.data?.primary_color || defaultTheme.primaryColor,
    secondaryColor: themeQuery.data?.secondary_color || defaultTheme.secondaryColor,
    buttonBg: themeQuery.data?.primary_color || defaultTheme.buttonBg,
    buttonText: defaultTheme.buttonText,
    logoUrl: themeQuery.data?.logo_url || menu.public_settings?.logo_url || null,
    coverUrl: themeQuery.data?.cover_url || menu.public_settings?.cover_image_url || null,
    slogan: themeQuery.data?.slogan || null,
    showLogoOnCover: themeQuery.data?.show_logo_on_cover ?? true,
  };

  const cssVariables = {
    "--primary-color": resolvedTheme.primaryColor,
    "--secondary-color": resolvedTheme.secondaryColor,
    "--button-bg": resolvedTheme.buttonBg,
    "--button-text": resolvedTheme.buttonText,
  } as CSSProperties;

  const allCategories = useMemo<PublicMenuCategory[]>(() => {
    const normalized = [...menu.categories];

    if (menu.items_without_category.length > 0) {
      normalized.push({
        id: -1,
        name: "Outros",
        sort_order: Number.MAX_SAFE_INTEGER,
        items: menu.items_without_category,
      });
    }

    return normalized;
  }, [menu.categories, menu.items_without_category]);

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
    <div className="min-h-screen bg-white pb-24 text-slate-800" style={cssVariables}>
      <StorefrontHero
        name={menu.tenant.name}
        slug={menu.slug}
        coverImageUrl={resolvedTheme.coverUrl}
        coverVideoUrl={menu.public_settings?.cover_video_url}
        logoUrl={resolvedTheme.logoUrl}
        slogan={resolvedTheme.slogan}
        showLogoOnCover={resolvedTheme.showLogoOnCover}
        isPreview={isPreview}
        isOpen={Boolean(menu.tenant.is_open)}
      />

      <div className="pt-12">
        <StorefrontCartBar
          storeName={menu.tenant.name}
          cartItemsCount={enableCart ? cartItemsCount : 0}
          totalLabel={`R$ ${(totalCents / 100).toFixed(2)}`}
          buttonColor="var(--button-bg)"
          onCartClick={openCart}
          onMenuClick={() => handleSelectCategory(allCategories[0]?.id ?? 0)}
        />

        <StorefrontCategoryTabs
          categories={allCategories}
          activeCategoryId={activeCategoryId}
          onSelectCategory={handleSelectCategory}
          primaryColor="var(--primary-color)"
        />

        <main className="mx-auto w-full max-w-6xl space-y-8 px-4 py-6">
          {allCategories.map((category) => (
            <section key={category.id} id={`category-${category.id}`} className="space-y-3 scroll-mt-28">
              <h2 className="text-lg font-semibold text-slate-900">{category.name}</h2>
              <div className="grid gap-4 md:grid-cols-2">
                {category.items.map((item) => (
                  <StorefrontProductCard
                    key={`${category.id}-${item.id}`}
                    item={item}
                    buttonColor="var(--button-bg)"
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
