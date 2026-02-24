export interface PublicMenuItem {
  id: number;
  category_id: number | null;
  name: string;
  description?: string | null;
  price_cents: number;
  image_url?: string | null;
  is_active?: boolean;
  is_popular?: boolean;
}

export interface PublicMenuCategory {
  id: number;
  name: string;
  sort_order: number;
  items: PublicMenuItem[];
}

export interface PublicSettings {
  cover_image_url?: string | null;
  cover_video_url?: string | null;
  logo_url?: string | null;
  theme?: string | null;
  primary_color?: string | null;
  secondary_color?: string | null;
  button_color?: string | null;
  hero_overlay_opacity?: number | null;
}

export interface PublicMenuResponse {
  tenant_id: number;
  slug: string;
  tenant: {
    id: number;
    slug: string;
    name: string;
    custom_domain?: string | null;
    is_open?: boolean | null;
  };
  public_settings?: PublicSettings | null;
  categories: PublicMenuCategory[];
  items_without_category: PublicMenuItem[];
  promo_code?: string | null;
  promo_description?: string | null;
}

export interface CartItem {
  item: PublicMenuItem;
  quantity: number;
}
