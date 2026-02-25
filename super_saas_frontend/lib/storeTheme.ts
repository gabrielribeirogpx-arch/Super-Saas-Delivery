interface StoreThemeConfig {
  primary_color?: string | null;
  secondary_color?: string | null;
  button_color?: string | null;
  cover_image_url?: string | null;
  logo_url?: string | null;
  hero_overlay_opacity?: number | null;
  banner_blur_enabled?: boolean | null;
  banner_blur_intensity?: number | null;
  banner_overlay_opacity?: number | null;
}

export interface StoreTheme {
  primaryColor: string;
  secondaryColor: string;
  buttonColor: string;
  coverImageUrl: string | null;
  logoUrl: string | null;
  heroOverlayOpacity: number;
  bannerBlurEnabled: boolean;
  bannerBlurIntensity: number;
  bannerOverlayOpacity: number;
}

export const themeDefaults: StoreTheme = {
  primaryColor: "#111827",
  secondaryColor: "#1F2937",
  buttonColor: "#1E40AF",
  coverImageUrl: null,
  logoUrl: null,
  heroOverlayOpacity: 0.55,
  bannerBlurEnabled: true,
  bannerBlurIntensity: 6,
  bannerOverlayOpacity: 0.55,
};

const isValidColor = (value?: string | null) =>
  typeof value === "string" && /^#([0-9A-Fa-f]{3}){1,2}$/.test(value.trim());

export function getStoreTheme(config?: StoreThemeConfig | null): StoreTheme {
  if (!config) {
    return themeDefaults;
  }

  const overlayOpacity =
    typeof config.hero_overlay_opacity === "number"
      ? Math.max(0, Math.min(1, config.hero_overlay_opacity))
      : themeDefaults.heroOverlayOpacity;

  const bannerBlurIntensity =
    typeof config.banner_blur_intensity === "number"
      ? Math.max(0, Math.min(32, config.banner_blur_intensity))
      : themeDefaults.bannerBlurIntensity;

  const bannerOverlayOpacity =
    typeof config.banner_overlay_opacity === "number"
      ? Math.max(0, Math.min(1, config.banner_overlay_opacity))
      : themeDefaults.bannerOverlayOpacity;

  return {
    primaryColor: isValidColor(config.primary_color)
      ? config.primary_color!.trim()
      : themeDefaults.primaryColor,
    secondaryColor: isValidColor(config.secondary_color)
      ? config.secondary_color!.trim()
      : themeDefaults.secondaryColor,
    buttonColor: isValidColor(config.button_color)
      ? config.button_color!.trim()
      : isValidColor(config.primary_color)
        ? config.primary_color!.trim()
        : themeDefaults.buttonColor,
    coverImageUrl: config.cover_image_url ?? themeDefaults.coverImageUrl,
    logoUrl: config.logo_url ?? themeDefaults.logoUrl,
    heroOverlayOpacity: overlayOpacity,
    bannerBlurEnabled: config.banner_blur_enabled ?? themeDefaults.bannerBlurEnabled,
    bannerBlurIntensity,
    bannerOverlayOpacity,
  };
}
