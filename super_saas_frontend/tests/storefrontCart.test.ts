import assert from "node:assert/strict";
import test from "node:test";

// @ts-ignore Node's native TypeScript runner requires the source extension.
import { clearStorefrontCart, getCartItemCount, getCartTotalInCents, getStorefrontCartKey, readStorefrontCart, writeStorefrontCart } from "../lib/storefrontCart.ts";

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
