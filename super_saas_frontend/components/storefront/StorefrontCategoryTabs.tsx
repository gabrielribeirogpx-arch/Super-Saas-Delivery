import { PublicMenuCategory } from "@/components/storefront/types";

interface StorefrontCategoryTabsProps {
  categories: PublicMenuCategory[];
  activeCategoryId: string;
  onSelectCategory: (id: string) => void;
  cartCount: number;
  showTopTab?: boolean;
}

export function StorefrontCategoryTabs({ categories, activeCategoryId, onSelectCategory, cartCount, showTopTab = true }: StorefrontCategoryTabsProps) {
  return (
    <nav className="sticky-nav">
      <div className="nav-inner">
        <div className="tabs-scroll" id="tabs-scroll">
          {showTopTab ? (
            <button type="button" onClick={() => onSelectCategory("top")} className={`tab ${activeCategoryId === "top" ? "active" : ""}`}>
              ⭐ Mais pedidos
            </button>
          ) : null}
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
