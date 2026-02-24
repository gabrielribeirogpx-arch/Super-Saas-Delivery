import { PublicMenuItem } from "@/components/storefront/types";
import { resolveMediaUrl } from "@/lib/media";

interface StorefrontProductCardProps {
  item: PublicMenuItem;
  onAdd?: (item: PublicMenuItem) => void;
  justAdded?: boolean;
  topPick?: boolean;
}

export function StorefrontProductCard({ item, onAdd, justAdded = false, topPick = false }: StorefrontProductCardProps) {
  const imageUrl = resolveMediaUrl(item.image_url);

  if (topPick) {
    return (
      <article className="product-card top-pick-card rounded-2xl border">
        {imageUrl ? (
          <img src={imageUrl} alt={item.name} loading="lazy" className="h-[clamp(130px,20vw,180px)] w-full rounded-t-2xl object-cover" />
        ) : (
          <div className="grid h-[clamp(130px,20vw,180px)] place-items-center rounded-t-2xl">🍽️</div>
        )}
        <div className="space-y-2 p-4">
          <p className="inline-flex rounded-[20px] px-2 py-1 text-xs">🔥 Popular</p>
          <h3 className="font-semibold">{item.name}</h3>
          {item.description && <p className="line-clamp-2 text-sm opacity-80">{item.description}</p>}
          <div className="flex items-center justify-between">
            <strong>R$ {(item.price_cents / 100).toFixed(2)}</strong>
            {onAdd && <button aria-label={`Adicionar ${item.name}`} type="button" className={`add-btn ${justAdded ? "added" : ""}`} onClick={() => onAdd(item)}>{justAdded ? "✓" : "+"}</button>}
          </div>
        </div>
      </article>
    );
  }

  return (
    <article className="product-row grid grid-cols-[clamp(58px,9.5vw,74px)_1fr_auto] items-center gap-3 rounded-[14px] border p-3">
      {imageUrl ? (
        <img src={imageUrl} alt={item.name} loading="lazy" className="h-[clamp(58px,9.5vw,74px)] w-[clamp(58px,9.5vw,74px)] rounded-[10px] object-cover" />
      ) : (
        <div className="grid h-[clamp(58px,9.5vw,74px)] w-[clamp(58px,9.5vw,74px)] place-items-center rounded-[10px]">🍽️</div>
      )}
      <div>
        <h3 className="font-semibold">{item.name}</h3>
        {item.description && <p className="text-sm opacity-80">{item.description}</p>}
      </div>
      <div className="text-right">
        <p className="mb-2 text-sm font-semibold">R$ {(item.price_cents / 100).toFixed(2)}</p>
        {onAdd && <button aria-label={`Adicionar ${item.name}`} type="button" className={`add-btn ${justAdded ? "added" : ""}`} onClick={() => onAdd(item)}>{justAdded ? "✓" : "+"}</button>}
      </div>
    </article>
  );
}
