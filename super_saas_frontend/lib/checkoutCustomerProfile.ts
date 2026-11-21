"use client";

export type CheckoutAddress = {
  id: number;
  zip: string;
  cep?: string;
  street: string;
  number: string;
  complement?: string;
  neighborhood: string;
  city: string;
  state: string;
  is_default?: boolean;
};

export type CheckoutCustomerProfile = {
  id: number;
  name: string;
  phone: string;
  email?: string;
  addresses: CheckoutAddress[];
};

const keyFor = (slug: string) => `storefront-checkout-profile:${slug}`;

export function loadCheckoutCustomerProfile(storage: Storage, slug: string): CheckoutCustomerProfile | null {
  try {
    const raw = storage.getItem(keyFor(slug)) ?? storage.getItem(`storefront-customer:${slug}`);
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (!value || typeof value.name !== "string" || typeof value.phone !== "string" || value.phone.replace(/\D/g, "").length < 10) return null;
    const addresses = Array.isArray(value.addresses) ? value.addresses.filter((entry: CheckoutAddress) =>
      entry && typeof entry.street === "string" && typeof entry.number === "string" && typeof entry.zip === "string"
    ) : [];
    return { id: Number(value.id) || 0, name: value.name, phone: value.phone, email: typeof value.email === "string" ? value.email : "", addresses };
  } catch {
    return null;
  }
}

export function saveCheckoutCustomerProfile(storage: Storage, slug: string, profile: CheckoutCustomerProfile) {
  try {
    storage.setItem(keyFor(slug), JSON.stringify(profile));
  } catch {
    // O pedido foi enviado; falha de armazenamento local não deve interromper a confirmação.
  }
}
