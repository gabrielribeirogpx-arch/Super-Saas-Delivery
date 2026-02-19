import { Button } from "@/components/ui/button";

interface StorefrontCartBarProps {
  storeName: string;
  cartItemsCount: number;
  totalLabel: string;
  buttonColor: string;
  onCartClick: () => void;
  onMenuClick: () => void;
}

export function StorefrontCartBar({
  storeName,
  cartItemsCount,
  totalLabel,
  buttonColor,
  onCartClick,
  onMenuClick,
}: StorefrontCartBarProps) {
  return (
    <>
      <div className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-4">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-900">{storeName}</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="md:hidden" onClick={onMenuClick}>
              ☰ Categorias
            </Button>
            <Button
              size="sm"
              className="rounded-xl"
              style={{ backgroundColor: buttonColor }}
              onClick={onCartClick}
            >
              Carrinho {cartItemsCount > 0 ? `(${cartItemsCount})` : ""}
            </Button>
          </div>
        </div>
      </div>

      {cartItemsCount > 0 && (
        <button
          type="button"
          onClick={onCartClick}
          className="fixed bottom-4 left-4 right-4 z-40 rounded-xl px-4 py-3 text-sm font-semibold text-white shadow-lg md:hidden"
          style={{ backgroundColor: buttonColor }}
        >
          Ver carrinho ({totalLabel})
        </button>
      )}
    </>
  );
}
