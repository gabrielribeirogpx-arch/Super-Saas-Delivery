export interface PublicMenuItem {
  id: number;
  category_id: number | null;
  name: string;
  description?: string | null;
  price_cents: number;
  image_url?: string | null;
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
  hero_mode?: string | null;
  hero_title?: string | null;
  hero_subtitle?: string | null;
  button_style?: string | null;
  layout_mode?: string | null;
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
}

export interface CartItem {
  item: PublicMenuItem;
  quantity: number;
}
