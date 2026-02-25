import { CSSProperties, useEffect, useState } from "react";

import { initBannerControls, initStoreStatus } from "@/components/storefront/storefrontEnhancements";
import { resolveMediaUrl } from "@/lib/media";

interface StorefrontHeroProps {
  store: {
    name: string;
    subtitle?: string | null;
    logoUrl?: string | null;
    isOpen?: boolean;
    estimatedTimeMin?: number | null;
  };
  coverImageUrl?: string | null;
  bannerBlurEnabled?: boolean;
  bannerBlurIntensity?: number;
  bannerOverlayOpacity?: number;
}

export function StorefrontHero({
  store,
  coverImageUrl,
  bannerBlurEnabled,
  bannerBlurIntensity,
  bannerOverlayOpacity,
}: StorefrontHeroProps) {
  const logoUrl = resolveMediaUrl(store.logoUrl);
  const resolvedCoverUrl = resolveMediaUrl(coverImageUrl);
  const [coverLoaded, setCoverLoaded] = useState(false);

  const status = initStoreStatus({
    isOpen: store.isOpen,
    estimatedTimeMin: store.estimatedTimeMin,
  });

  const bannerStyles = initBannerControls({
    bannerBlurEnabled,
    bannerBlurIntensity,
    bannerOverlayOpacity,
  }) as CSSProperties;

  useEffect(() => {
    if (!resolvedCoverUrl) {
      setCoverLoaded(false);
      return;
    }

    const img = new Image();
    img.onload = () => setCoverLoaded(true);
    img.src = resolvedCoverUrl;
  }, [resolvedCoverUrl]);

  return (
    <div className="store-banner" style={bannerStyles}>
      {coverLoaded && resolvedCoverUrl ? (
        <img src={resolvedCoverUrl} id="cover-photo" alt={`Banner da loja ${store.name}`} />
      ) : (
        <div className="store-banner-placeholder" id="cover-photo" />
      )}
      <div className="banner-overlay" />

      <div className="store-hero-content">
        <div className="store-avatar" id="avatar" aria-label={`Logo ${store.name}`}>
          {logoUrl ? <img src={logoUrl} alt={store.name} /> : <span>{store.name.charAt(0).toUpperCase()}</span>}
        </div>

        <div className="store-info">
          <h1 className="store-name" id="resto-name">
            {store.name}
          </h1>
          <span className="store-meta" id="resto-slug">
            {store.subtitle ?? "@loja • Cardápio"}
          </span>
          <div className="store-status-row">
            <span className={status.badgeClassName}>{status.badgeText}</span>
            <span className="wait-time">{status.waitTime}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
