import { PublicMenuItem } from "@/components/storefront/types";
import { resolveMediaUrl } from "@/lib/media";

interface StorefrontProductCardProps {
  item: PublicMenuItem;
  onAdd?: (item: PublicMenuItem) => void;
  justAdded?: boolean;
  topPick?: boolean;
}

export const formatPrice = (value: number) => (value / 100).toFixed(2).replace(".", ",");

const tagStyle = (tag: string) => {
  if (/🔥|Popular/.test(tag)) return { background: "#fff7ed", color: "#c2410c" };
  if (/⭐|Destaque/.test(tag)) return { background: "#fefce8", color: "#92400e" };
  if (/Novo/.test(tag)) return { background: "#eff6ff", color: "#1d4ed8" };
  if (/🌿|Vegano|Natural/.test(tag)) return { background: "#f0fdf4", color: "#166534" };
  if (/🌶|Picante/.test(tag)) return { background: "#fef2f2", color: "#b91c1c" };
  if (/Premium/.test(tag)) return { background: "#faf5ff", color: "#6d28d9" };
  if (/💰|Economize/.test(tag)) return { background: "#ecfdf5", color: "#065f46" };
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
      <article className="feat-card" aria-label={item.name} role={onAdd ? "button" : undefined} tabIndex={onAdd ? 0 : undefined} onClick={onAdd ? () => onAdd(item) : undefined} onKeyDown={onAdd ? (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onAdd(item);
        }
      } : undefined}>
        <div className="feat-img-wrap">
          {imageUrl ? <img src={imageUrl} alt={item.name} loading="lazy" /> : <div className="feat-img-ph">🍽️</div>}
        </div>
        <div className="feat-body">
          {tags[0] && (
            <span className="feat-tag" style={tagStyle(tags[0])}>
              {tags[0]}
            </span>
          )}
          <div className="feat-name">{item.name}</div>
          {item.description && <div className="feat-desc">{item.description}</div>}
          <div className="feat-foot">
            <div className="feat-price">
              <small>R$</small>
              {formatPrice(item.price_cents)}
            </div>
            {onAdd && (
              <button type="button" className={`btn-add ${justAdded ? "added" : ""}`} onClick={(event) => {
                event.stopPropagation();
                onAdd(item);
              }}>
                {justAdded ? "✓" : "+"}
              </button>
            )}
          </div>
        </div>
      </article>
    );
  }

  return (
    <article className="menu-item" aria-label={item.name} data-name={item.name.toLowerCase()} data-desc={(item.description ?? "").toLowerCase()} role={onAdd ? "button" : undefined} tabIndex={onAdd ? 0 : undefined} onClick={onAdd ? () => onAdd(item) : undefined} onKeyDown={onAdd ? (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onAdd(item);
      }
    } : undefined}>
      {imageUrl ? <img className="item-thumb" src={imageUrl} alt={item.name} loading="lazy" /> : <div className="item-thumb-ph">🍽️</div>}
      <div className="item-info">
        <div className="item-name">{item.name}</div>
        {item.description && <div className="item-desc">{item.description}</div>}
        {tags.length > 0 && (
          <div className="item-tags">
            {tags.map((tag) => (
              <span key={`${item.id}-${tag}`} className="item-tag" style={tagStyle(tag)}>
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="item-action">
        <div className="item-price">
          <small>R$</small>
          {formatPrice(item.price_cents)}
        </div>
        {onAdd && (
          <button type="button" className={`btn-add ${justAdded ? "added" : ""}`} onClick={(event) => {
            event.stopPropagation();
            onAdd(item);
          }}>
            {justAdded ? "✓" : "+"}
          </button>
        )}
      </div>
    </article>
  );
}
