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
    <>
      <div className="cover-band">
        <div
          className={`cover-photo ${coverLoaded ? "loaded" : ""}`}
          id="cover-photo"
          style={coverLoaded && resolvedCoverUrl ? { backgroundImage: `url('${resolvedCoverUrl}')` } : undefined}
        />
        <div className="cover-dots" />
        <div className="cover-fade" />
      </div>

      <div className="identity-wrap">
        <div className="identity-card">
          <div className="avatar" id="avatar" aria-label={`Logo ${store.name}`}>
            {logoUrl ? <img src={logoUrl} alt={store.name} /> : store.name.charAt(0).toUpperCase()}
          </div>
          <div className="resto-info">
            <div className="resto-name" id="resto-name">
              {store.name}
            </div>
            <div className="resto-sub">
              {store.subtitle && (
                <span className="resto-slug" id="resto-slug">
                  {store.subtitle}
                </span>
              )}
              {store.subtitle && <span className="sep">·</span>}
              <span className="resto-rating-inline">
                <span className="star">★</span>
                <span id="rating-val">{store.rating ?? "4.9"}</span>
                <span className="rc" id="rating-count">
                  ({store.totalReviews ?? "312"})
                </span>
              </span>
            </div>
            <div className="badges-row" id="badges-row">
              {store.isOpen ? (
                <span className="badge b-open">
                  <span className="pulse" />
                  Aberto agora
                </span>
              ) : (
                <span className="badge b-closed">● Fechado no momento</span>
              )}
              <span className="badge b-time">⏱ {store.delivery ?? "~30 min"}</span>
              <span className="badge b-fee">🛵 {store.fee ?? "Grátis"}</span>
            </div>
          </div>
          <div className="identity-right" id="identity-right" />
        </div>
      </div>
    </>
  );
}
