import { useEffect, useState } from "react";

import { resolveMediaUrl } from "@/lib/media";

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
  coverImageUrl?: string | null;
}

export function StorefrontHero({ store, coverImageUrl }: StorefrontHeroProps) {
  const logoUrl = resolveMediaUrl(store.logoUrl);
  const resolvedCoverUrl = resolveMediaUrl(coverImageUrl);
  const [coverLoaded, setCoverLoaded] = useState(false);

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
    <header className="hero" id="hero">
      <div className="hero-bg" />
      <div
        className={`hero-cover ${coverLoaded ? "loaded" : ""}`}
        id="hero-cover"
        style={coverLoaded && resolvedCoverUrl ? { backgroundImage: `url('${resolvedCoverUrl}')` } : undefined}
      />
      <div className="hero-dots" />
      <div className="hero-content">
        <div className="avatar" id="avatar" aria-label={`Logo ${store.name}`}>
          {logoUrl ? <img src={logoUrl} alt={store.name} /> : store.name.charAt(0).toUpperCase()}
        </div>
        <div className="resto-info">
          <div className="resto-name" id="resto-name">
            {store.name}
          </div>
          {store.subtitle && (
            <div className="resto-slug" id="resto-slug">
              {store.subtitle}
            </div>
          )}
          <div className="resto-rating">
            <span className="star">★</span>
            <span id="rating-val">{store.rating ?? "4.9"}</span>
            <span className="rating-count" id="rating-count">
              ({store.totalReviews ?? "312"} avaliações)
            </span>
          </div>
          <div className="badges-row" id="badges-row">
            {store.isOpen ? (
              <span className="badge badge-open">
                <span className="pulse" />
                Aberto agora
              </span>
            ) : (
              <span className="badge badge-closed">● Fechado no momento</span>
            )}
            <span className="badge badge-time">⏱ {store.delivery ?? "~30 min"}</span>
            <span className="badge badge-fee">🛵 {store.fee ?? "Grátis"}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
