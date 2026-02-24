import { PublicMenuItem } from "@/components/storefront/types";
import { resolveMediaUrl } from "@/lib/media";

interface StorefrontProductCardProps {
  item: PublicMenuItem;
  onAdd?: (item: PublicMenuItem) => void;
  justAdded?: boolean;
  topPick?: boolean;
}

const formatPrice = (value: number) =>
  new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value / 100);

const tagStyle = (tag: string) => {
  if (tag.includes("🔥") || tag.includes("Popular")) return { background: "#fff7ed", color: "#c2410c" };
  if (tag.includes("⭐") || tag.includes("Destaque")) return { background: "#fefce8", color: "#92400e" };
  if (tag.includes("Novo") || tag.includes("New")) return { background: "#eff6ff", color: "#1d4ed8" };
  if (tag.includes("🌿") || tag.includes("Vegano")) return { background: "#f0fdf4", color: "#166534" };
  if (tag.includes("🌶") || tag.includes("Picante")) return { background: "#fef2f2", color: "#b91c1c" };
  if (tag.includes("Premium")) return { background: "#faf5ff", color: "#6d28d9" };
  if (tag.includes("💰") || tag.includes("Economize")) return { background: "#ecfdf5", color: "#065f46" };
  return { background: "var(--surface2)", color: "var(--muted)" };
};

const buildTags = (item: PublicMenuItem, topPick: boolean) => {
  if (item.tags?.length) return item.tags;
  if (topPick || item.is_popular) return ["🔥 Popular"];
  return [];
};

export function StorefrontProductCard({ item, onAdd, justAdded = false, topPick = false }: StorefrontProductCardProps) {
  const imageUrl = resolveMediaUrl(item.image_url);
  const tags = buildTags(item, topPick);

  if (topPick) {
    return (
      <article className="feat-card" aria-label={item.name}>
        {imageUrl ? (
          <img src={imageUrl} alt={item.name} loading="lazy" className="feat-image" />
        ) : (
          <div className="feat-image feat-placeholder">🍽️</div>
        )}
        <div className="space-y-2 p-4">
          {tags[0] && (
            <span className="tag-chip" style={tagStyle(tags[0])}>
              {tags[0]}
            </span>
          )}
          <h3 className="item-name">{item.name}</h3>
          {item.description && <p className="item-desc clamp-2">{item.description}</p>}
          <div className="mt-1 flex items-center justify-between">
            <strong className="item-price">{formatPrice(item.price_cents)}</strong>
            {onAdd && (
              <button aria-label={`Adicionar ${item.name}`} type="button" className={`btn-add ${justAdded ? "added" : ""}`} onClick={() => onAdd(item)}>
                {justAdded ? "✓" : "+"}
              </button>
            )}
          </div>
        </div>
      </article>
    );
  }

  return (
    <article className="menu-item" aria-label={item.name}>
      {imageUrl ? <img src={imageUrl} alt={item.name} loading="lazy" className="menu-thumb" /> : <div className="menu-thumb menu-thumb-placeholder">🍽️</div>}
      <div className="min-w-0">
        <h3 className="menu-item-name truncate">{item.name}</h3>
        {item.description && <p className="menu-item-desc truncate">{item.description}</p>}
        {tags.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1.5">
            {tags.map((tag) => (
              <span key={`${item.id}-${tag}`} className="tag-chip" style={tagStyle(tag)}>
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="text-right">
        <p className="item-price mb-2">{formatPrice(item.price_cents)}</p>
        {onAdd && (
          <button aria-label={`Adicionar ${item.name}`} type="button" className={`btn-add ${justAdded ? "added" : ""}`} onClick={() => onAdd(item)}>
            {justAdded ? "✓" : "+"}
          </button>
        )}
      </div>
    </article>
  );
}
