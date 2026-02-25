import { CSSProperties, MouseEvent } from "react";

interface StoreStatusInput {
  isOpen?: boolean | null;
  estimatedTimeMin?: number | null;
}

interface BannerControlsInput {
  bannerBlurEnabled?: boolean | null;
  bannerBlurIntensity?: number | null;
  bannerOverlayOpacity?: number | null;
}

interface MobileMenuControlsInput {
  setIsOpen: (value: boolean | ((current: boolean) => boolean)) => void;
}

export function initStoreStatus({ isOpen, estimatedTimeMin }: StoreStatusInput) {
  const isStoreOpen = Boolean(isOpen);
  const badgeText = isStoreOpen ? "Aberto agora" : "Fechado";
  const badgeClassName = `status-badge ${isStoreOpen ? "open" : "closed"}`;
  const waitTime = typeof estimatedTimeMin === "number" && estimatedTimeMin > 0 ? `~${estimatedTimeMin} min` : "~30 min";

  return {
    badgeText,
    badgeClassName,
    waitTime,
  };
}

export function initBannerControls({
  bannerBlurEnabled,
  bannerBlurIntensity,
  bannerOverlayOpacity,
}: BannerControlsInput): CSSProperties {
  const normalizedBlur = typeof bannerBlurIntensity === "number" ? Math.max(0, Math.min(32, bannerBlurIntensity)) : 6;
  const normalizedOverlay = typeof bannerOverlayOpacity === "number" ? Math.max(0, Math.min(1, bannerOverlayOpacity)) : 0.55;

  return {
    "--blur": bannerBlurEnabled === false ? "0px" : `${normalizedBlur}px`,
    "--overlay": String(normalizedOverlay),
  } as CSSProperties;
}

export function initMobileMenu({ setIsOpen }: MobileMenuControlsInput) {
  const openMenu = () => setIsOpen(true);
  const closeMenu = () => setIsOpen(false);
  const toggleMenu = () => setIsOpen((current) => !current);
  const handleBackdropClick = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      closeMenu();
    }
  };

  return { openMenu, closeMenu, toggleMenu, handleBackdropClick };
}
