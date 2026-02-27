import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { PublicMenuCategory } from "@/components/storefront/types";

interface StorefrontCategoryTabsProps {
  categories: PublicMenuCategory[];
  activeCategoryId: string;
  onSelectCategory: (id: string) => void;
  cartCount: number;
}

export function StorefrontCategoryTabs({ categories, activeCategoryId, onSelectCategory, cartCount }: StorefrontCategoryTabsProps) {
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    document.body.style.overflow = isSheetOpen ? "hidden" : "";

    return () => {
      document.body.style.overflow = "";
    };
  }, [isSheetOpen]);

  const handleCategoryClick = (categoryId: string) => {
    onSelectCategory(categoryId);
    setIsSheetOpen(false);
  };

  const openSheet = () => setIsSheetOpen(true);
  const closeSheet = () => setIsSheetOpen(false);

  return (
    <nav className="sticky-nav">
      <div className="nav-inner">
        <button type="button" className="mobile-category-toggle" id="mobileCategoryToggle" onClick={openSheet}>
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

        <button type="button" className="cart-btn" onClick={() => onSelectCategory("storefront-cart")}>
          🛒 Carrinho
          <span className="cart-pill" id="cart-count-nav">
            {cartCount}
          </span>
        </button>
      </div>

      {isMounted
        ? createPortal(
            <>
              <div id="categorySheetOverlay" className={`category-overlay ${isSheetOpen ? "open" : ""}`} onClick={closeSheet} />
              <div id="categorySheet" className={`category-sheet ${isSheetOpen ? "open" : ""}`}>
                <div className="sheet-drag-indicator" />
                <div className="sheet-header">
                  <h3>Categorias</h3>
                  <button type="button" id="closeCategorySheet" onClick={closeSheet}>
                    ✕
                  </button>
                </div>
                <div className="sheet-body" id="sheetCategoryList">
                  {categories.map((category) => (
                    <button
                      type="button"
                      key={`mobile-${category.id}`}
                      onClick={() => handleCategoryClick(String(category.id))}
                      className={activeCategoryId === String(category.id) ? "active" : ""}
                    >
                      {category.emoji ?? "🍽️"} {category.name}
                    </button>
                  ))}
                </div>
              </div>
            </>,
            document.body,
          )
        : null}
    </nav>
  );
}
