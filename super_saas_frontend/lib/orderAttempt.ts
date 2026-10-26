// Persist only a random key and a digest. Never store checkout form fields here.
const PREFIX = "fomizero:order-attempt:v1:";
const MAX_AGE = 7 * 24 * 60 * 60 * 1000;
type Attempt = { key: string; digest: string; createdAt: number };
type Completion = { scope: string; attempt: Attempt };
const memory = new Map<string, Attempt>();
const completions = new WeakMap<object, Completion>();
export class OrderAttemptError extends Error {}
export class UnconfirmedOrderAttemptError extends OrderAttemptError {}

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value)
    .filter(([, entry]) => entry !== undefined).sort(([a], [b]) => a.localeCompare(b))
    .map(([key, entry]) => [key, canonical(entry)]));
  return value;
}

function storage() {
  try { return typeof window !== "undefined" ? window.localStorage : null; } catch { return null; }
}

function read(scope: string): Attempt | null {
  const cached = memory.get(scope);
  try {
    const raw = storage()?.getItem(PREFIX + scope);
    if (raw) {
      const entry = JSON.parse(raw);
      if (typeof entry.key === "string" && /^[a-zA-Z0-9_-]{32,128}$/.test(entry.key)
          && /^[a-f0-9]{64}$/.test(entry.digest) && Number.isFinite(entry.createdAt)) return entry;
    }
  } catch { /* Memory fallback keeps the same attempt during this page lifetime. */ }
  return cached || null;
}

export async function orderAttempt(scope: string, payload: unknown): Promise<Attempt & { reused: boolean }> {
  if (!globalThis.crypto?.subtle || !globalThis.crypto?.randomUUID) {
    throw new OrderAttemptError("Não foi possível iniciar o pedido com segurança. Recarregue a página.");
  }
  const bytes = new TextEncoder().encode(JSON.stringify(canonical(payload)));
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  const digest = Array.from(new Uint8Array(hash), value => value.toString(16).padStart(2, "0")).join("");
  const previous = read(scope);
  if (previous && previous.digest !== digest) {
    throw new UnconfirmedOrderAttemptError("Há um pedido sem confirmação com outros dados. Confira com a loja antes de iniciar outro pedido.");
  }
  if (previous?.digest === digest) {
    // Do not silently generate a fresh key for an old, ambiguous attempt.
    if (Date.now() - previous.createdAt >= MAX_AGE) throw new UnconfirmedOrderAttemptError("Esta tentativa é antiga. Confira seus pedidos com a loja antes de fazer outro pedido.");
    memory.set(scope, previous);
    return { ...previous, reused: true };
  }
  const next = { key: crypto.randomUUID(), digest, createdAt: Date.now() };
  memory.set(scope, next);
  try { storage()?.setItem(PREFIX + scope, JSON.stringify(next)); } catch { /* Memory fallback. */ }
  return { ...next, reused: false };
}

export function startNewOrderAttempt(scope: string) {
  memory.delete(scope);
  try { storage()?.removeItem(PREFIX + scope); } catch { /* Current-page fallback. */ }
}

export function rejectFirstOrderAttempt(scope: string, attempt: Attempt & { reused: boolean }, status: number) {
  // A first, definitive validation rejection created no order. An uncertain or
  // replayed attempt must never be discarded merely because a later call fails.
  if (!attempt.reused && status >= 400 && status < 500 && status !== 409 && read(scope)?.key === attempt.key) {
    startNewOrderAttempt(scope);
  }
}

export function rememberOrderResponse(response: object, scope: string, attempt: Attempt) {
  completions.set(response, { scope, attempt });
}

// Called only after the UI saved the confirmation and cleared the old cart.
export function completeOrderAttempt(response: unknown) {
  if (!response || typeof response !== "object") return;
  const completion = completions.get(response);
  if (!completion) return;
  const { scope, attempt } = completion;
  if (read(scope)?.key === attempt.key) {
    memory.delete(scope);
    try { storage()?.removeItem(PREFIX + scope); } catch { /* Already completed in memory. */ }
  }
  completions.delete(response);
}
