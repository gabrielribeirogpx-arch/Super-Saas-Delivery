import type { CSSProperties } from "react";

import { resolveMediaUrl } from "@/lib/media";
import { themeDefaults, type StoreTheme } from "@/lib/storeTheme";

interface StorefrontHeroProps {
  store: { name: string; subtitle?: string | null; logoUrl?: string | null; isOpen?: boolean };
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
    <header className="relative min-h-[260px] overflow-hidden md:min-h-[340px]" style={heroStyle}>
      {coverImageUrl && <img src={coverImageUrl} alt={`Capa da loja ${store.name}`} className="hero-cover absolute inset-0 h-full w-full object-cover" />}
      {!coverImageUrl && <div className="absolute inset-0 bg-[linear-gradient(160deg,#1f2937_0%,#0f172a_100%)]" />}
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(0,0,0,.12)_0%,rgba(0,0,0,.62)_100%)]" />

      <div className="relative mx-auto flex min-h-[260px] w-full max-w-6xl items-end gap-3 px-4 pb-6 text-white md:min-h-[340px]">
        {logoUrl ? (
          <img src={logoUrl} alt={`Logo ${store.name}`} className="h-20 w-20 rounded-[14px] border-[3px] border-white object-cover" />
        ) : (
          <div className="grid h-20 w-20 place-items-center rounded-[14px] border-[3px] border-white bg-black/30 text-2xl font-bold">{store.name.charAt(0).toUpperCase()}</div>
        )}
        <div>
          <h1 className="font-display text-3xl font-bold md:text-4xl">{store.name}</h1>
          {store.subtitle && <p className="text-sm text-white/90">{store.subtitle}</p>}
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            {store.isOpen ? (
              <span className="inline-flex items-center gap-1 rounded-[20px] bg-black/35 px-3 py-1"><span className="pulse-dot h-2 w-2 rounded-full bg-emerald-400" />Aberto agora</span>
            ) : (
              <span className="rounded-[20px] bg-black/35 px-3 py-1 text-red-300">Fechado no momento</span>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
