import assert from "node:assert/strict";
import test from "node:test";

// @ts-ignore Node's native TypeScript runner requires the source extension.
import { addConfiguredCartItem, clearStorefrontCart, decrementOrRemoveCartItem, getCartItemCount, getCartLineIdentity, getCartTotalInCents, getStorefrontCartKey, readStorefrontCart, writeStorefrontCart } from "../lib/storefrontCart.ts";

class MemoryStorage {
  private values = new Map<string, string>();

  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); }
  removeItem(key: string) { this.values.delete(key); }
}

const product = { quantity: 1, totalPrice: 47.9 };

test("primeira abertura inicia com carrinho vazio, contagem e total zerados", () => {
  const cart = readStorefrontCart<typeof product>(new MemoryStorage(), "fomizero");
  assert.deepEqual(cart, []);
  assert.equal(getCartItemCount(cart), 0);
  assert.equal(getCartTotalInCents(cart), 0);
  assert.equal(getCartItemCount(cart) > 0, false, "a barra deve permanecer oculta");
});

test("adicionar o primeiro produto exibe a barra e calcula o total", () => {
  const cart = [product];
  assert.equal(getCartItemCount(cart), 1);
  assert.equal(getCartTotalInCents(cart), 4790);
  assert.equal(getCartItemCount(cart) > 0, true);
});

test("remover o último produto volta a ocultar a barra", () => {
  const cart = [product].filter((_, index) => index !== 0);
  assert.equal(getCartItemCount(cart), 0);
  assert.equal(getCartTotalInCents(cart), 0);
  assert.equal(getCartItemCount(cart) > 0, false);
});

test("recarregar restaura um carrinho em andamento", () => {
  const storage = new MemoryStorage();
  writeStorefrontCart(storage, "fomizero", [product]);
  assert.deepEqual(readStorefrontCart(storage, "fomizero"), [product]);
});

test("carrinhos são isolados por loja", () => {
  const storage = new MemoryStorage();
  writeStorefrontCart(storage, "loja-a", [product]);
  assert.equal(getStorefrontCartKey("loja-a"), "mobile-storefront-cart:loja-a");
  assert.deepEqual(readStorefrontCart(storage, "loja-b"), []);
});

test("pedido concluído não é restaurado em um refresh", () => {
  const storage = new MemoryStorage();
  writeStorefrontCart(storage, "fomizero", [product]);
  clearStorefrontCart(storage, "fomizero");
  assert.deepEqual(readStorefrontCart(storage, "fomizero"), []);
});

const configuredItem = (overrides: Record<string, unknown> = {}) => ({
  id: "10-configured",
  menuItemId: 10,
  name: "Burger House",
  price: 20,
  quantity: 1,
  modifiers: [{ groupId: 2, groupName: "Adicionais", optionId: 7, optionName: "Bacon", price: 3, quantity: 1 }],
  note: "sem cebola",
  totalPrice: 23,
  ...overrides,
});

test("menos reduz quantidade maior que um e recalcula o total", () => {
  const cart = decrementOrRemoveCartItem([configuredItem({ quantity: 2, totalPrice: 46 })], 0);
  assert.equal(cart[0].quantity, 1);
  assert.equal(cart[0].totalPrice, 23);
});

test("menos remove uma linha com quantidade um, inclusive quando é a única", () => {
  const cart = decrementOrRemoveCartItem([configuredItem()], 0);
  assert.deepEqual(cart, []);
  assert.equal(getCartItemCount(cart), 0);
  assert.equal(getCartTotalInCents(cart), 0);
});

test("configurações diferentes do mesmo produto permanecem em linhas separadas", () => {
  const withoutBacon = configuredItem({ id: "10-plain", modifiers: [], note: "" });
  const withBacon = configuredItem();
  const cart = addConfiguredCartItem(addConfiguredCartItem([], withoutBacon), withBacon);
  assert.equal(cart.length, 2);
  assert.notEqual(getCartLineIdentity(withoutBacon), getCartLineIdentity(withBacon));
});

test("configuração idêntica agrega quantidade sem perder modifiers, preços e observação", () => {
  const cart = addConfiguredCartItem([configuredItem()], configuredItem({ id: "new-id", quantity: 2, totalPrice: 46 }));
  assert.equal(cart.length, 1);
  assert.equal(cart[0].quantity, 3);
  assert.equal(cart[0].totalPrice, 69);
  assert.equal(cart[0].modifiers[0].optionName, "Bacon");
  assert.equal(cart[0].note, "sem cebola");
});

test("refresh preserva a configuração completa e remoção persiste carrinho vazio", () => {
  const storage = new MemoryStorage();
  writeStorefrontCart(storage, "fomizero", [configuredItem()]);
  const restored = readStorefrontCart<ReturnType<typeof configuredItem>>(storage, "fomizero");
  assert.deepEqual(restored[0].modifiers, configuredItem().modifiers);
  assert.equal(restored[0].totalPrice, 23);
  writeStorefrontCart(storage, "fomizero", decrementOrRemoveCartItem(restored, 0));
  assert.deepEqual(readStorefrontCart(storage, "fomizero"), []);
});

test("carrinho legado sem modifiers e observação continua válido", () => {
  const legacy = { id: 10, menuItemId: 10, quantity: 1, totalPrice: 20 };
  assert.doesNotThrow(() => getCartLineIdentity(legacy));
  assert.deepEqual(decrementOrRemoveCartItem([legacy], 0), []);
});
