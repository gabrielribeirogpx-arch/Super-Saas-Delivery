// @ts-ignore Node native TypeScript tests import source extensions.
import { isFiniteTrackingNumber, formatTrackingEta } from "../lib/trackingPresentation.ts";
import assert from "node:assert/strict";
// @ts-ignore Node's native TypeScript runner requires the source extension.
import { normalizeTrackingStatus, resolveTrackingStep } from "../lib/orderTrackingStatus.ts";
import test from "node:test";

// @ts-ignore Node's native TypeScript runner requires the source extension.
import {
  endPublicOrderSubmission,
  PUBLIC_ORDER_ERROR_MESSAGE,
  PUBLIC_ORDER_ENDPOINT,
  submitPublicOrder,
  tryBeginPublicOrderSubmission,
} from "../lib/publicCheckout.ts";
// @ts-ignore Node's native TypeScript runner requires the source extension.
import { buildStorefrontApiUrl } from "../lib/storefrontApi.ts";

const validPayload = {
  customer_phone: "11999999999",
  delivery_type: "RETIRADA",
  items: [{ item_id: 1, quantity: 1 }],
};

test("checkout usa exatamente a rota publica canonica com o tenant slug", async () => {
  const originalFetch = globalThis.fetch;
  let capturedUrl = "";
  let capturedHeaders: Headers | undefined;
  globalThis.fetch = async (input, init) => {
    capturedUrl = String(input);
    capturedHeaders = new Headers(init?.headers);
    return new Response(JSON.stringify({ order_id: 42, status: "pending" }), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await submitPublicOrder<{ order_id: number }>(validPayload, "tempero");
    assert.equal(PUBLIC_ORDER_ENDPOINT, "/public/orders");
    assert.equal(capturedUrl, "/api/public/orders?tenant=tempero");
    assert.equal(capturedHeaders?.get("x-tenant-id"), "tempero");
    assert.equal(result.order_id, 42);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("erro do backend rejeita a finalizacao sem executar efeitos de sucesso", async () => {
  const originalFetch = globalThis.fetch;
  let successEffects = 0;
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: "Loja indisponível" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });

  try {
    await assert.rejects(
      submitPublicOrder(validPayload, "tempero").then(() => { successEffects += 1; }),
      /Loja indisponível/,
    );
    assert.equal(successEffects, 0, "o chamador não deve limpar o carrinho no fluxo de sucesso");
    assert.equal(PUBLIC_ORDER_ERROR_MESSAGE, "Não foi possível finalizar seu pedido. Tente novamente.");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("normalizacao do endpoint preserva um unico prefixo /api", () => {
  assert.equal(buildStorefrontApiUrl(PUBLIC_ORDER_ENDPOINT, "tempero"), "/api/public/orders?tenant=tempero");
});

test("bloqueio de submit impede duas requisicoes simultaneas e libera nova tentativa", () => {
  const lock = { current: false };
  assert.equal(tryBeginPublicOrderSubmission(lock), true);
  assert.equal(tryBeginPublicOrderSubmission(lock), false);
  endPublicOrderSubmission(lock);
  assert.equal(tryBeginPublicOrderSubmission(lock), true);
});

test("checkout recognizes delivery-start statuses without returning to pending", () => {
  for (const raw of ["OUT_FOR_DELIVERY", "out_for_delivery", "SAIU", "saiu", "SAIU_PARA_ENTREGA", "delivering"]) {
    assert.equal(normalizeTrackingStatus(raw), "delivering", raw);
    assert.equal(resolveTrackingStep(raw), 4, raw);
  }
  assert.equal(normalizeTrackingStatus("ENTREGUE"), "delivered");
  assert.equal(resolveTrackingStep("ENTREGUE"), 5);
});

test("tracking does not invent ETA or GPS coordinates from missing values", () => {
  for (const missing of [null, undefined, "", false, NaN, Infinity]) {
    assert.equal(isFiniteTrackingNumber(missing), false);
  }
  assert.equal(isFiniteTrackingNumber(0), true);
  assert.equal(formatTrackingEta(null, null), null);
  assert.equal(formatTrackingEta(undefined, undefined), null);
  assert.equal(formatTrackingEta(0, 0), null);
  assert.equal(formatTrackingEta(-1, -10), null);
  assert.equal(formatTrackingEta(120, 1500), "Chegando em 2 min • 1.5 km");
});
