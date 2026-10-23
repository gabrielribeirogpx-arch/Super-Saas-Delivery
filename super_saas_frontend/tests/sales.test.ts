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
