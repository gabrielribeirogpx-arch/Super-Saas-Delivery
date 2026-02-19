import { Button } from "@/components/ui/button";
import { PublicMenuItem } from "@/components/storefront/types";
import { resolveMediaUrl } from "@/lib/media";

interface StorefrontProductCardProps {
  item: PublicMenuItem;
  buttonColor?: string;
  onAdd?: (item: PublicMenuItem) => void;
}

export function StorefrontProductCard({
  item,
  buttonColor = "var(--button-bg)",
  onAdd,
}: StorefrontProductCardProps) {
  const imageUrl = resolveMediaUrl(item.image_url);

  return (
    <article className="flex flex-col md:flex-row overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      {imageUrl && (
        <img
          src={imageUrl}
          alt={item.name}
          className="h-44 w-full object-cover md:h-full md:w-40 md:shrink-0"
        />
      )}

      <div className={`flex flex-1 flex-col gap-3 p-4 ${imageUrl ? "md:flex-row" : ""}`}>
        <div className="flex-1">
          <h3 className="text-base font-semibold text-slate-900">{item.name}</h3>
          {item.description && (
            <p className="mt-1 line-clamp-2 text-sm text-slate-500">{item.description}</p>
          )}
        </div>

        <div className="mt-auto flex items-center justify-between gap-3">
          <p className="text-base font-bold text-slate-900">
            R$ {(item.price_cents / 100).toFixed(2)}
          </p>
          {onAdd && (
            <Button
              size="sm"
              className="rounded-xl px-4 shadow-sm"
              style={{ backgroundColor: buttonColor }}
              onClick={() => onAdd(item)}
            >
              Adicionar
            </Button>
          )}
        </div>
      </div>
    </article>
  );
}
