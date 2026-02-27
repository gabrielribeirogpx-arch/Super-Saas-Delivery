import { useState } from "react";

import { PublicMenuCategory } from "@/components/storefront/types";

interface StorefrontCategoryTabsProps {
  categories: PublicMenuCategory[];
  activeCategoryId: string;
  onSelectCategory: (id: string) => void;
  cartCount: number;
}

export function StorefrontCategoryTabs({ categories, activeCategoryId, onSelectCategory, cartCount }: StorefrontCategoryTabsProps) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const handleCategoryClick = (categoryId: string) => {
    onSelectCategory(categoryId);
    setIsDrawerOpen(false);
  };

  return (
    <nav className="sticky-nav">
      <div className="nav-inner">
        <button type="button" className="mobile-category-toggle" id="mobileCategoryToggle" onClick={() => setIsDrawerOpen((prev) => !prev)}>
          ☰ Categorias
        </button>

        <div id="categories-bar" className="categories-bar category-scroll-container">
          {categories.map((category) => (
            <button
              type="button"
              key={category.id}
              onClick={() => handleCategoryClick(String(category.id))}
              className={`tab ${activeCategoryId === String(category.id) ? "active" : ""}`}
            >
              {category.emoji ?? "🍽️"} {category.name}
            </button>
          ))}
        </div>

        <div className={`mobile-category-drawer ${isDrawerOpen ? "open" : ""}`} id="mobileCategoryDrawer">
          {categories.map((category) => (
            <button
              type="button"
              key={`mobile-${category.id}`}
              onClick={() => handleCategoryClick(String(category.id))}
              className={`tab ${activeCategoryId === String(category.id) ? "active" : ""}`}
            >
              {category.emoji ?? "🍽️"} {category.name}
            </button>
          ))}
        </div>
        {isDrawerOpen && <button type="button" className="mobile-category-backdrop" aria-label="Fechar categorias" onClick={() => setIsDrawerOpen(false)} />}

        <button type="button" className="cart-btn" onClick={() => onSelectCategory("storefront-cart")}>
          🛒 Carrinho
          <span className="cart-pill" id="cart-count-nav">
            {cartCount}
          </span>
        </button>
      </div>
    </nav>
  );
}
