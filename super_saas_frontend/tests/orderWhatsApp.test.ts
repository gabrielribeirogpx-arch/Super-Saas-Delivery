declare function require(name: string): any;

const assert = require("node:assert/strict");
const test = require("node:test");

import {
  buildOrderWhatsAppUrl,
  getOrderWhatsAppTemplate,
  normalizeWhatsAppPhone,
  renderOrderWhatsAppMessage,
} from "../lib/orderWhatsApp";

const baseOrder = {
  id: 42,
  daily_order_number: 7,
  cliente_nome: "Maria",
  cliente_telefone: "(16) 99999-9999",
  status: "RECEBIDO",
  valor_total: 2590,
  endereco: "Rua A, 123",
};

test("telefone brasileiro com máscara gera URL correta", () => {
  const url = buildOrderWhatsAppUrl(baseOrder);
  assert.ok(url?.startsWith("https://wa.me/5516999999999?text="));
});

test("telefone com +55 gera URL correta", () => {
  assert.equal(normalizeWhatsAppPhone("+55 16 99999-9999"), "5516999999999");
});

test("telefone já normalizado não recebe 55 duplicado", () => {
  assert.equal(normalizeWhatsAppPhone("5516999999999"), "5516999999999");
});

test("telefone inválido desabilita ação", () => {
  assert.equal(normalizeWhatsAppPhone("9999"), null);
  assert.equal(buildOrderWhatsAppUrl({ ...baseOrder, cliente_telefone: "9999" }), null);
});

test("mensagem de pending usa template correto", () => {
  assert.equal(getOrderWhatsAppTemplate("RECEBIDO"), "Olá, {cliente}! Recebemos o seu pedido #{pedido}. Em breve iniciaremos o atendimento.");
});

test("mensagem de preparing usa template correto", () => {
  const message = renderOrderWhatsAppMessage(getOrderWhatsAppTemplate("EM_PREPARO"), { cliente: "Ana", pedido: 9 });
  assert.equal(message, "Olá, Ana! Seu pedido #9 já está sendo preparado.");
});

test("mensagem de delivered usa template correto", () => {
  const message = renderOrderWhatsAppMessage(getOrderWhatsAppTemplate("DELIVERED"), { cliente: "Ana", pedido: 9 });
  assert.equal(message, "Olá, Ana! Seu pedido #9 foi entregue. Obrigado pela preferência!");
});

test("variáveis são substituídas corretamente", () => {
  assert.equal(renderOrderWhatsAppMessage("{cliente} #{pedido} {total} {loja}", { cliente: "João", pedido: 3, total: "R$ 10,00", loja: "Loja" }), "João #3 R$ 10,00 Loja");
});

test("valor ausente não gera undefined", () => {
  const message = renderOrderWhatsAppMessage("Olá, {cliente}! {previsao}", { cliente: undefined, previsao: null });
  assert.equal(message.includes("undefined"), false);
  assert.equal(message, "Olá, ! ");
});

test("texto é codificado com encodeURIComponent", () => {
  const message = "Olá, Maria! Seu pedido #7 foi confirmado.";
  const url = buildOrderWhatsAppUrl({ ...baseOrder, status: "CONFIRMADO" });
  assert.ok(url?.endsWith(`text=${encodeURIComponent(message)}`));
});
