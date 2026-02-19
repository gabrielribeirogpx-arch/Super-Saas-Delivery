interface StoreThemeConfig {
  primary_color?: string | null;
  secondary_color?: string | null;
  button_color?: string | null;
  cover_image_url?: string | null;
  logo_url?: string | null;
}

export interface StoreTheme {
  primaryColor: string;
  secondaryColor: string;
  buttonColor: string;
  coverImageUrl: string | null;
  logoUrl: string | null;
}

const DEFAULT_THEME: StoreTheme = {
  primaryColor: "#111827",
  secondaryColor: "#1F2937",
  buttonColor: "#1E40AF",
  coverImageUrl: null,
  logoUrl: null,
};

const isValidColor = (value?: string | null) =>
  typeof value === "string" && /^#([0-9A-Fa-f]{3}){1,2}$/.test(value.trim());

export function getStoreTheme(config?: StoreThemeConfig | null): StoreTheme {
  if (!config) {
    return DEFAULT_THEME;
  }

  return {
    primaryColor: isValidColor(config.primary_color)
      ? config.primary_color!.trim()
      : DEFAULT_THEME.primaryColor,
    secondaryColor: isValidColor(config.secondary_color)
      ? config.secondary_color!.trim()
      : DEFAULT_THEME.secondaryColor,
    buttonColor: isValidColor(config.button_color)
      ? config.button_color!.trim()
      : isValidColor(config.primary_color)
        ? config.primary_color!.trim()
        : DEFAULT_THEME.buttonColor,
    coverImageUrl: config.cover_image_url ?? DEFAULT_THEME.coverImageUrl,
    logoUrl: config.logo_url ?? DEFAULT_THEME.logoUrl,
  };
}
