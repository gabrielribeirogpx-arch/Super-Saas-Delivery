export interface StorefrontCartEntry {
  quantity: number;
  totalPrice: number;
}

export interface CartStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export const getStorefrontCartKey = (slug: string) => `mobile-storefront-cart:${slug}`;

export const getCartItemCount = (items: Pick<StorefrontCartEntry, "quantity">[]) =>
  items.reduce((sum, item) => sum + item.quantity, 0);

export const getCartTotalInCents = (items: StorefrontCartEntry[]) =>
  items.reduce((sum, item) => sum + Math.round(item.totalPrice * 100), 0);

export function readStorefrontCart<T>(storage: CartStorage, slug: string): T[] {
  try {
    const stored = storage.getItem(getStorefrontCartKey(slug));
    if (!stored) return [];
    const parsed: unknown = JSON.parse(stored);
    return Array.isArray(parsed) ? parsed as T[] : [];
  } catch {
    return [];
  }
}

export function writeStorefrontCart<T>(storage: CartStorage, slug: string, items: T[]) {
  storage.setItem(getStorefrontCartKey(slug), JSON.stringify(items));
}

export function clearStorefrontCart(storage: CartStorage, slug: string) {
  storage.removeItem(getStorefrontCartKey(slug));
}
