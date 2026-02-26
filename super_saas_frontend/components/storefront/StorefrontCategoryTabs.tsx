import { useState } from "react";

import { initMobileMenu } from "@/components/storefront/storefrontEnhancements";
import { PublicMenuCategory } from "@/components/storefront/types";

interface StorefrontCategoryTabsProps {
  categories: PublicMenuCategory[];
  activeCategoryId: string;
  onSelectCategory: (id: string) => void;
  cartCount: number;
}

export function StorefrontCategoryTabs({ categories, activeCategoryId, onSelectCategory, cartCount }: StorefrontCategoryTabsProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const mobileMenu = initMobileMenu({ setIsOpen: setIsMobileMenuOpen });

  const handleSelectCategory = (id: string) => {
    onSelectCategory(id);
    mobileMenu.closeMenu();
  };

  return (
    <nav className="sticky-nav">
      <div className="nav-inner">
        <button
          type="button"
          className="mobile-menu-btn"
          onClick={mobileMenu.toggleMenu}
          aria-label="Abrir categorias"
          aria-expanded={isMobileMenuOpen}
        >
          ☰
        </button>

        <div id="categories-bar" className="categories-bar">
          {categories.map((category) => (
            <button
              type="button"
              key={category.id}
              onClick={() => onSelectCategory(String(category.id))}
              className={`tab ${activeCategoryId === String(category.id) ? "active" : ""}`}
            >
              {category.emoji ?? "🍽️"} {category.name}
            </button>
          ))}
        </div>

        <button type="button" className="cart-btn" onClick={() => onSelectCategory("storefront-cart")}>
          🛒 Carrinho
          <span className="cart-pill" id="cart-count-nav">
            {cartCount}
          </span>
        </button>
      </div>

      <div className={`mobile-drawer-overlay ${isMobileMenuOpen ? "open" : ""}`} onClick={mobileMenu.handleBackdropClick}>
        <aside className={`mobile-categories-drawer ${isMobileMenuOpen ? "open" : ""}`} aria-hidden={!isMobileMenuOpen}>
          <div className="mobile-drawer-header">
            <strong>Categorias</strong>
            <button type="button" onClick={mobileMenu.closeMenu} className="mobile-drawer-close" aria-label="Fechar categorias">
              ✕
            </button>
          </div>

          <div className="mobile-drawer-list">
            {categories.map((category) => (
              <button
                type="button"
                key={`mobile-${category.id}`}
                onClick={() => handleSelectCategory(String(category.id))}
                className={`mobile-drawer-item ${activeCategoryId === String(category.id) ? "active" : ""}`}
              >
                <span>{category.emoji ?? "🍽️"}</span>
                <span>{category.name}</span>
              </button>
            ))}
          </div>
        </aside>
      </div>
    </nav>
  );
}
