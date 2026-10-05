import assert from "node:assert/strict";
import test from "node:test";

import { hasOptionalCustomization, hasRequiredCustomization, shouldOpenCustomization } from "../lib/productCustomization.ts";

const item = (groups: any[] = []) => ({ id: 1, category_id: null, name: "Produto", price_cents: 1000, modifier_groups: groups });
const option = { id: 1, name: "Bacon", price_delta: 3, is_default: false, is_active: true, order_index: 0 };

test("produto sem modificadores não exige personalização", () => {
  assert.equal(hasRequiredCustomization(item()), false);
  assert.equal(hasOptionalCustomization(item()), false);
  assert.equal(shouldOpenCustomization(item()), false);
});

test("required ou min_selection positivo exige personalização", () => {
  assert.equal(hasRequiredCustomization(item([{ id: 1, name: "Ponto", required: true, min_selection: 0, max_selection: 1, options: [option] }])), true);
  assert.equal(hasRequiredCustomization(item([{ id: 1, name: "Sabores", required: false, min_selection: 1, max_selection: 2, options: [option] }])), true);
});

test("grupo opcional útil abre a personalização antes de adicionar", () => {
  const optional = item([{ id: 1, name: "Adicionais", required: false, min_selection: 0, max_selection: 2, options: [option] }]);
  assert.equal(hasRequiredCustomization(optional), false);
  assert.equal(hasOptionalCustomization(optional), true);
  assert.equal(shouldOpenCustomization(optional), true);
});

test("grupo sem opções ativas não abre personalização", () => {
  const empty = item([{ id: 1, name: "Adicionais", required: true, min_selection: 1, max_selection: 1, options: [] }]);
  assert.equal(hasRequiredCustomization(empty), false);
  assert.equal(hasOptionalCustomization(empty), false);
  assert.equal(shouldOpenCustomization(empty), false);
});
