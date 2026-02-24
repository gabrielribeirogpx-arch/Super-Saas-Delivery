import { PublicMenuCategory } from "@/components/storefront/types";

interface StorefrontCategoryTabsProps {
  categories: PublicMenuCategory[];
  activeCategoryId: string;
  onSelectCategory: (id: string) => void;
  primaryColor: string;
  cartCount: number;
}

export function StorefrontCategoryTabs({ categories, activeCategoryId, onSelectCategory, primaryColor, cartCount }: StorefrontCategoryTabsProps) {
  return (
    <div className="no-scrollbar overflow-x-auto border-b">
      <div className="mx-auto flex w-full max-w-6xl items-center gap-2 px-4 py-2">
        <button
          type="button"
          onClick={() => onSelectCategory("top-picks")}
          className="relative whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium"
          style={{ color: activeCategoryId === "top-picks" ? primaryColor : undefined }}
        >
          ⭐ Mais pedidos
        </button>
        {categories.map((category) => (
          <button
            type="button"
            key={category.id}
            onClick={() => onSelectCategory(String(category.id))}
            className="relative whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium"
            style={{ color: activeCategoryId === String(category.id) ? primaryColor : undefined }}
          >
            🍽️ {category.name}
          </button>
        ))}
        <button type="button" className="ml-auto shrink-0 rounded-[50px] px-3 py-2 text-sm font-semibold">
          🛒 Carrinho ({cartCount})
        </button>
      </div>
    </div>
  );
}
