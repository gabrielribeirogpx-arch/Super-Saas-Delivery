export interface StorefrontCartEntry {
  quantity: number;
  totalPrice: number;
}

export interface ConfiguredCartEntry extends StorefrontCartEntry {
  id: string | number;
  menuItemId?: number;
  note?: string;
  modifiers?: Array<{ groupId: number; optionId: number; quantity: number }> | string[];
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

/** A cart line is the product plus its complete, immutable customization. */
export function getCartLineIdentity(item: ConfiguredCartEntry): string {
  const modifiers = (item.modifiers ?? [])
    .map((modifier) => typeof modifier === "string"
      ? { groupId: 0, optionId: modifier, quantity: 1 }
      : { groupId: modifier.groupId, optionId: modifier.optionId, quantity: modifier.quantity })
    .sort((a, b) => `${a.groupId}:${a.optionId}`.localeCompare(`${b.groupId}:${b.optionId}`));

  return JSON.stringify({
    productId: item.menuItemId ?? item.id,
    modifiers,
    note: (item.note ?? "").trim(),
  });
}

export function addConfiguredCartItem<T extends ConfiguredCartEntry>(items: T[], incoming: T): T[] {
  const identity = getCartLineIdentity(incoming);
  const existingIndex = items.findIndex((item) => getCartLineIdentity(item) === identity);
  if (existingIndex < 0) return [...items, incoming];

  const current = items[existingIndex];
  const updated = [...items];
  updated[existingIndex] = {
    ...current,
    quantity: current.quantity + incoming.quantity,
    totalPrice: current.totalPrice + incoming.totalPrice,
  };
  return updated;
}

export function decrementOrRemoveCartItem<T extends StorefrontCartEntry>(items: T[], index: number): T[] {
  const current = items[index];
  if (!current) return items;
  if (current.quantity <= 1) return items.filter((_, itemIndex) => itemIndex !== index);

  const updated = [...items];
  updated[index] = {
    ...current,
    quantity: current.quantity - 1,
    totalPrice: current.totalPrice / current.quantity * (current.quantity - 1),
  };
  return updated;
}

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
