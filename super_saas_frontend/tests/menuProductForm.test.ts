import assert from "node:assert/strict";
import test from "node:test";
import { parseMenuPriceCents } from "../lib/menuProductForm.ts";

test("mobile price entry accepts Brazilian and decimal formats without changing the charged amount", () => {
  assert.equal(parseMenuPriceCents("29,90"), 2990);
  assert.equal(parseMenuPriceCents("29.90"), 2990);
  assert.equal(parseMenuPriceCents("R$ 1.234,56"), 123456);
  assert.equal(parseMenuPriceCents("0"), 0);
  for (const invalid of ["", "abc", "29,999", "-1", "1.234.56"]) {
    assert.equal(parseMenuPriceCents(invalid), null);
  }
});
