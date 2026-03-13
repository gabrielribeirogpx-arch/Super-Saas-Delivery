export const getCustomerStorageKey = (slug: string) => `storefront-customer:${slug}`;

export type CustomerSession = {
  customerId: number;
  name?: string;
  phone?: string;
  email?: string;
};

export const loadCustomerSession = (slug: string): CustomerSession | null => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(getCustomerStorageKey(slug));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CustomerSession;
    if (!parsed?.customerId) return null;
    return parsed;
  } catch {
    return null;
  }
};

export const saveCustomerSession = (slug: string, payload: CustomerSession) => {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(getCustomerStorageKey(slug), JSON.stringify(payload));
};
