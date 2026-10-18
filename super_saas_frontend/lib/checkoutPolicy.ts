import { storefrontFetch } from './storefrontApi.ts';
export type CheckoutMethod = { id: string; label: string; available: boolean };
export type CheckoutPolicy = { methods: CheckoutMethod[]; message: string | null };
const ids = new Set(['pix', 'money', 'card', 'native_pix', 'native_card']);
export function parseCheckoutPolicy(value: unknown): CheckoutPolicy {
  if (!value || typeof value !== 'object') throw new Error('Formas de pagamento indisponíveis');
  const data = value as Record<string, unknown>;
  if (!Array.isArray(data.methods)) throw new Error('Formas de pagamento indisponíveis');
  const seen = new Set<string>();
  const methods = data.methods.map((entry: unknown) => {
    if (!entry || typeof entry !== 'object') throw new Error('Forma de pagamento inválida');
    const method = entry as Record<string, unknown>;
    if (typeof method.id !== 'string' || !ids.has(method.id) || seen.has(method.id) || typeof method.label !== 'string' || !method.label.trim() || typeof method.available !== 'boolean') throw new Error('Forma de pagamento inválida');
    seen.add(method.id);
    return { id: method.id, label: method.label, available: method.available };
  });
  return { methods, message: typeof data.message === 'string' ? data.message : null };
}
export async function fetchCheckoutPolicy(tenant: string, signal?: AbortSignal) {
  const response = await storefrontFetch('/public/checkout-policy', { cache: 'no-store', signal }, tenant);
  if (!response.ok) throw new Error('Não foi possível carregar as formas de pagamento. Tente novamente.');
  return parseCheckoutPolicy(await response.json());
}
export function canUseCheckoutMethod(policy: CheckoutPolicy | null, method: string) {
  return policy?.methods.some(option => option.id === method && option.available) === true;
}
