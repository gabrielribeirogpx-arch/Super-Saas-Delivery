interface StoreThemeConfig {
  primary_color?: string | null;
  secondary_color?: string | null;
  cover_image_url?: string | null;
  logo_url?: string | null;
  hero_mode?: string | null;
  hero_title?: string | null;
  hero_subtitle?: string | null;
  button_style?: string | null;
  layout_mode?: string | null;
}

export interface StoreTheme {
  primaryColor: string;
  secondaryColor: string;
  coverImageUrl: string | null;
  logoUrl: string | null;
  heroMode: string;
  heroTitle: string;
  heroSubtitle: string;
  buttonStyle: string;
  layoutMode: string;
}

export const themeDefaults: StoreTheme = {
  primaryColor: "#2563eb",
  secondaryColor: "#111827",
  coverImageUrl: null,
  logoUrl: null,
  heroMode: "commercial",
  heroTitle: "",
  heroSubtitle: "",
  buttonStyle: "rounded",
  layoutMode: "hybrid",
};

const isValidColor = (value?: string | null) =>
  typeof value === "string" && /^#([0-9A-Fa-f]{3}){1,2}$/.test(value.trim());

export function getStoreTheme(config?: StoreThemeConfig | null): StoreTheme {
  if (!config) {
    return themeDefaults;
  }

  return {
    primaryColor: isValidColor(config.primary_color)
      ? config.primary_color!.trim()
      : themeDefaults.primaryColor,
    secondaryColor: isValidColor(config.secondary_color)
      ? config.secondary_color!.trim()
      : themeDefaults.secondaryColor,
    coverImageUrl: config.cover_image_url ?? themeDefaults.coverImageUrl,
    logoUrl: config.logo_url ?? themeDefaults.logoUrl,
    heroMode: config.hero_mode || themeDefaults.heroMode,
    heroTitle: config.hero_title || themeDefaults.heroTitle,
    heroSubtitle: config.hero_subtitle || themeDefaults.heroSubtitle,
    buttonStyle: config.button_style || themeDefaults.buttonStyle,
    layoutMode: config.layout_mode || themeDefaults.layoutMode,
  };
}
