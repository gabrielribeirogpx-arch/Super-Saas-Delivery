import type { CSSProperties } from "react";

import { resolveMediaUrl } from "@/lib/media";
import { type StoreTheme, themeDefaults } from "@/lib/storeTheme";

interface StorefrontHeroProps {
  store: {
    name: string;
    subtitle?: string | null;
    logoUrl?: string | null;
    isOpen?: boolean;
    delivery?: string;
    fee?: string;
    rating?: string;
    totalReviews?: string;
  };
  theme?: StoreTheme | null;
}

export function StorefrontHero({ store, theme }: StorefrontHeroProps) {
  const safeTheme = theme ?? themeDefaults;
  const coverImageUrl = resolveMediaUrl(safeTheme.coverImageUrl);
  const logoUrl = resolveMediaUrl(store.logoUrl ?? safeTheme.logoUrl);

  const heroStyle = {
    "--accent": safeTheme.primaryColor || themeDefaults.primaryColor,
  } as CSSProperties;

  return (
    <header className="header-bg relative overflow-hidden border-b" style={heroStyle}>
      {coverImageUrl && <div className="header-cover absolute inset-0" style={{ backgroundImage: `url(${coverImageUrl})` }} />}
      <div className="header-overlay absolute inset-0" />

      <div className="relative mx-auto flex w-full max-w-6xl flex-wrap items-center gap-4 px-4 py-7 md:py-10">
        {logoUrl ? (
          <img src={logoUrl} alt={`Logo ${store.name}`} className="header-logo" />
        ) : (
          <div className="header-logo header-logo-fallback" aria-label={`Inicial ${store.name}`}>
            {store.name.charAt(0).toUpperCase()}
          </div>
        )}

        <div className="min-w-0 flex-1">
          <h1 className="header-title">{store.name}</h1>
          {store.subtitle && <p className="header-subtitle">{store.subtitle}</p>}
          <p className="header-meta">★ {store.rating ?? "4.9"} ({store.totalReviews ?? "312"} avaliações)</p>

          <div className="mt-3 flex flex-wrap gap-2">
            <span className={`badge ${store.isOpen ? "badge-open" : "badge-closed"}`}>{store.isOpen ? "Aberto" : "Fechado"}</span>
            <span className="badge badge-delivery">{store.delivery ?? "~30 min"}</span>
            <span className="badge badge-fee">{store.fee ?? "Grátis"}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
