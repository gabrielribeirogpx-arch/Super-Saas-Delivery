import { PublicMenuCategory } from "@/components/storefront/types";

interface StorefrontCategoryTabsProps {
  categories: PublicMenuCategory[];
  activeCategoryId: string;
  onSelectCategory: (id: string) => void;
  cartCount: number;
}

export function StorefrontCategoryTabs({ categories, activeCategoryId, onSelectCategory, cartCount }: StorefrontCategoryTabsProps) {
  return (
    <div className="sticky-nav no-scrollbar overflow-x-auto">
      <div className="mx-auto flex w-full max-w-6xl items-center gap-1 px-4 py-2 md:gap-2">
        <button type="button" onClick={() => onSelectCategory("top-picks")} className={`tab-btn ${activeCategoryId === "top-picks" ? "active" : ""}`}>
          ⭐ Mais pedidos
        </button>
        {categories.map((category) => (
          <button
            type="button"
            key={category.id}
            onClick={() => onSelectCategory(String(category.id))}
            className={`tab-btn ${activeCategoryId === String(category.id) ? "active" : ""}`}
          >
            {category.emoji ?? "🍽️"} {category.name}
          </button>
        ))}

        <button type="button" className="cart-pill ml-auto shrink-0" onClick={() => onSelectCategory("storefront-cart")}>
          🛒 Carrinho
          <span className="cart-badge">{cartCount}</span>
        </button>
      </div>
    </div>
  );
}
