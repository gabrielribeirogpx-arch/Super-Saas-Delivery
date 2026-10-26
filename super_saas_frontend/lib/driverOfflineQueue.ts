import { api } from "@/lib/api";

const QUEUE_KEY = "driver-pending-actions-v1";
const STATE_KEY = "driver-state-cache-v1";

type PendingAction = {
  id: string;
  path: string;
  method: "POST";
  body?: unknown;
  createdAt: string;
};

function readQueue(): PendingAction[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]") as PendingAction[]; } catch { return []; }
}

function writeQueue(queue: PendingAction[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
  window.dispatchEvent(new CustomEvent("driver:pending-actions", { detail: queue.length }));
}

export function getPendingDriverActionCount() {
  return readQueue().length;
}

export function enqueueDriverAction(path: string, body?: unknown) {
  const action: PendingAction = { id: `${Date.now()}-${Math.random().toString(36).slice(2)}`, path, method: "POST", body, createdAt: new Date().toISOString() };
  writeQueue([...readQueue(), action]);
}

export async function flushPendingDriverActions() {
  if (typeof window === "undefined" || !navigator.onLine) return;
  const queue = readQueue();
  const remaining: PendingAction[] = [];
  for (const action of queue) {
    try { await api.post(action.path, action.body); } catch { remaining.push(action); }
  }
  writeQueue(remaining);
}

export function cacheDriverState<T>(state: T) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STATE_KEY, JSON.stringify({ savedAt: new Date().toISOString(), state }));
}

export function readCachedDriverState<T>() {
  if (typeof window === "undefined") return null;
  try { return (JSON.parse(localStorage.getItem(STATE_KEY) || "null") as { state: T } | null)?.state ?? null; } catch { return null; }
}
