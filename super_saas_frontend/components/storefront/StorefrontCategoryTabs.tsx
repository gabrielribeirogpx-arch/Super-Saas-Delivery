import { PublicMenuCategory } from "@/components/storefront/types";

interface StorefrontCategoryTabsProps {
  categories: PublicMenuCategory[];
  activeCategoryId: string;
  onSelectCategory: (id: string) => void;
  cartCount: number;
}

export function StorefrontCategoryTabs({ categories, activeCategoryId, onSelectCategory, cartCount }: StorefrontCategoryTabsProps) {
  return (
    <nav className="sticky-nav">
      <div className="nav-inner">
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
    </nav>
  );
}
