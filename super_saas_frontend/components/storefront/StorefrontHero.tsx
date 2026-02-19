import type { CSSProperties } from "react";

import { resolveMediaUrl } from "@/lib/media";
import { themeDefaults, type StoreTheme } from "@/lib/storeTheme";

interface StorefrontHeroProps {
  store: {
    name: string;
    subtitle?: string | null;
    logoUrl?: string | null;
    isOpen?: boolean;
  };
  theme?: StoreTheme | null;
  onCartClick?: () => void;
}

const clampOpacity = (value: unknown) => {
  const parsed = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(parsed)) {
    return 0.55;
  }

  return Math.max(0, Math.min(1, parsed));
};

export function StorefrontHero({ store, theme, onCartClick }: StorefrontHeroProps) {
  const safeTheme = theme ?? themeDefaults;
  const coverImageUrl = resolveMediaUrl(safeTheme.coverImageUrl);
  const logoUrl = resolveMediaUrl(store.logoUrl ?? safeTheme.logoUrl);
  const overlayOpacity = clampOpacity(safeTheme.heroOverlayOpacity);

  const heroStyle = {
    "--primary": safeTheme.primaryColor || themeDefaults.primaryColor,
    "--bg": safeTheme.secondaryColor || themeDefaults.secondaryColor,
    "--surface": safeTheme.buttonColor || themeDefaults.buttonColor,
    "--radius-card": "24px",
    "--radius-button": "999px",
    backgroundImage: coverImageUrl
      ? `url(${coverImageUrl})`
      : "linear-gradient(160deg, var(--bg) 0%, var(--primary) 100%)",
    backgroundSize: "cover",
    backgroundPosition: "center",
  } as CSSProperties;

  return (
    <header className="relative min-h-[220px] overflow-hidden md:min-h-[320px]" style={heroStyle}>
      <div
        className="absolute inset-0"
        style={{
          background: `linear-gradient(180deg, rgba(0,0,0,${Math.max(0.16, overlayOpacity - 0.2)}) 0%, rgba(0,0,0,${overlayOpacity}) 100%)`,
        }}
      />

      <div className="relative mx-auto flex min-h-[220px] w-full max-w-[1200px] flex-col items-center justify-end px-4 pb-6 text-white md:min-h-[320px] md:pb-8">
        {logoUrl && (
          <img
            src={logoUrl}
            alt={`Logo ${store.name}`}
            className="h-24 w-24 rounded-full border-4 border-white object-cover shadow-lg md:h-[120px] md:w-[120px]"
          />
        )}

        <div className="mt-4 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-white md:text-4xl">{store.name}</h1>
          {store.subtitle && <p className="mt-2 text-sm text-white/85 md:text-base">{store.subtitle}</p>}
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-center gap-2" style={{ borderRadius: "var(--radius-card)" }}>
          {store.isOpen && (
            <span
              className="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold text-white"
              style={{ backgroundColor: "var(--surface)" }}
            >
              Aberto agora
            </span>
          )}

          {onCartClick && (
            <button
              type="button"
              onClick={onCartClick}
              className="px-5 py-2 text-sm font-semibold text-white transition-transform duration-200 hover:-translate-y-0.5"
              style={{
                backgroundColor: "var(--primary)",
                borderRadius: "var(--radius-button)",
                boxShadow: "0 8px 18px rgba(0,0,0,0.2)",
              }}
            >
              Ver carrinho
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
