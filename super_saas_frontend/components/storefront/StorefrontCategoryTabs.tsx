import { PublicMenuCategory } from "@/components/storefront/types";

interface StorefrontCategoryTabsProps {
  categories: PublicMenuCategory[];
  activeCategoryId: number | null;
  onSelectCategory: (id: number) => void;
}

export function StorefrontCategoryTabs({
  categories,
  activeCategoryId,
  onSelectCategory,
}: StorefrontCategoryTabsProps) {
  if (categories.length === 0) {
    return null;
  }

  return (
    <div className="no-scrollbar overflow-x-auto border-b border-slate-200 bg-white">
      <div className="mx-auto flex w-full max-w-6xl gap-2 px-4 py-2">
        {categories.map((category) => {
          const isActive = activeCategoryId === category.id;

          return (
            <button
              key={category.id}
              onClick={() => onSelectCategory(category.id)}
              className="relative whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition hover:text-slate-900"
              style={{ color: isActive ? "var(--primary-color)" : undefined }}
            >
              {category.name}
              <span
                className="absolute inset-x-2 -bottom-[2px] h-[2px] origin-left rounded-full transition-transform"
                style={{
                  backgroundColor: "var(--primary-color)",
                  transform: isActive ? "scaleX(1)" : "scaleX(0)",
                }}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}
