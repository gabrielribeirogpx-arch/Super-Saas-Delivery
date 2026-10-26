import assert from "node:assert/strict";
import test from "node:test";
import { safeLocalRedirect, selectedPlan } from "../lib/sales.ts";
test("preserves a selected plan through a safe local login redirect", () => {
  assert.equal(selectedPlan("operation"), "operation");
  assert.equal(selectedPlan("https://evil.example"), null);
  assert.equal(safeLocalRedirect("/subscriptions?plan=operation"), "/subscriptions?plan=operation");
});
test("login refuses external and browser-normalized network path redirects", () => {
  for (const value of [null, "https://evil.example", "//evil.example", "/\\evil.example", "/\t/evil.example", "javascript:alert(1)"]) {
    assert.equal(safeLocalRedirect(value), "/dashboard");
  }
});

test("recent store is only an optional validated public address hint", async () => {
  const { rememberStore, recentStore } = await import("../lib/recentStore.ts");
  const values = new Map<string,string>();
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: {
    setItem: (key: string, value: string) => values.set(key, value), getItem: (key: string) => values.get(key) ?? null,
  } });
  rememberStore("minha-pizzaria");
  assert.equal(recentStore(), "minha-pizzaria");
  assert.deepEqual([...values.values()], ["minha-pizzaria"]);
  rememberStore("//evil.example");
  assert.equal(recentStore(), "minha-pizzaria");
  values.set("fomizero:recent-store:v1", "https://evil.example");
  assert.equal(recentStore(), "");
  Object.defineProperty(globalThis, "localStorage", { configurable: true, get() { throw new Error("storage blocked"); } });
  assert.doesNotThrow(() => rememberStore("restaurante"));
  assert.equal(recentStore(), "");
  delete (globalThis as {localStorage?: unknown}).localStorage;
});
