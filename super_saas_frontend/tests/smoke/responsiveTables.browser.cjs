// Fixtures only: never reaches a live backend, provider or payment service.
const puppeteer = require("puppeteer-core");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const base =
  process.env.RESPONSIVE_TABLES_TEST_BASE_URL || "http://127.0.0.1:3047";
const artifacts =
  process.env.RESPONSIVE_TABLES_ARTIFACT_DIR ||
  path.join(os.tmpdir(), "fomizero-responsive-tables");
fs.mkdirSync(artifacts, { recursive: true });
const now = new Date().toISOString();
const name = "Hambúrguer artesanal da casa com acompanhamento";
const reason =
  "Ajuste de estoque conferido na operação. " +
  "Detalhamento preservado para consulta. ".repeat(7);
const review = {
  billing_event_id: 7001,
  provider: "kiwify",
  event_type: "order_approved",
  order_id: "synthetic-order",
  external_subscription_id: null,
  product_id: "synthetic-product",
  external_offer_id: null,
  candidate_plan_id: 1,
  candidate_plan_name: "Plano de demonstração",
  candidate_tenant_id: 1,
  verification_status: "manual_review",
  received_at: now,
  occurred_at: now,
  sale_checked_at: now,
  sale_status: "paid",
  period_start: null,
  period_end: null,
  reason: "trusted_period_missing",
  can_approve: false,
  access_pending_period: true,
  approval_blockers: ["trusted_period_missing"],
  decision: null,
  decided_by: null,
  decided_at: null,
  rejection_reason: null,
};
const payment = {
  id: 9,
  order_id: 9,
  order_number: 4,
  method: "cash",
  amount_cents: 2990,
  status: "pending",
  order_status: "DELIVERED",
  created_at: now,
  paid_at: null,
  confirmed_by: null,
  can_confirm: true,
  can_cancel: true,
  can_refund: false,
};
const routes = [
  ["/inventory", 2],
  ["/reports", 2],
  ["/finance", 2],
  ["/users", 1],
  ["/admin/1/delivery-users", 1],
  ["/audit", 1],
  ["/whatsapp", 1],
  ["/ai", 1],
  ["/marketing/coupons", 1],
  ["/marketing/rewards", 1],
  ["/subscriptions/reviews", 1],
];
async function fixturePage(browser, width, mode = "normal") {
  const page = await browser.newPage();
  const errors = [],
    writes = [];
  await page.setViewport({ width, height: 900 });
  await page.setBypassServiceWorker(true);
  await page.evaluateOnNewDocument(() => {
    delete Navigator.prototype.serviceWorker;
  });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.setRequestInterception(true);
  page.on("request", (request) => {
    const u = new URL(request.url());
    const send = (data, status = 200) =>
      request.respond({
        status,
        contentType: "application/json",
        body: JSON.stringify(data),
      });
    if (u.pathname.startsWith("/api/") && request.method() !== "GET") {
      writes.push(u.pathname);
      return send({ detail: "Unexpected write in read-only fixture" }, 500);
    }
    if (u.pathname === "/api/admin/auth/me")
      return send({
        id: 1,
        tenant_id: 1,
        name: "Marina Souza",
        role: "admin",
        active: true,
      });
    if (u.pathname === "/api/admin/billing/access")
      return send({ managed: false, active: true, features: {} });
    if (mode === "error" && u.pathname.startsWith("/api/inventory/"))
      return send({ detail: "Synthetic read failure" }, 503);
    if (u.pathname === "/api/inventory/items")
      return send(
        mode === "empty"
          ? []
          : [
              {
                id: 1,
                name,
                unit: "kg",
                current_stock: 2,
                min_stock_level: 5,
                cost_cents: 1500,
              },
            ],
      );
    if (u.pathname === "/api/inventory/movements")
      return send(
        mode === "empty"
          ? []
          : [
              {
                id: 1,
                item_name: name,
                type: "out",
                quantity: 2,
                reason,
                created_at: now,
              },
            ],
      );
    if (u.pathname === "/api/reports/financial/summary")
      return send({
        gross_revenue_cents: 2990,
        net_revenue_cents: 2500,
        orders_count: 2,
        average_ticket_cents: 1495,
        fees_cents: 490,
        cogs_cents: 0,
      });
    if (u.pathname === "/api/reports/sales/top-items")
      return send({ items: [{ name, qty: 2, gross_revenue_cents: 2990 }] });
    if (u.pathname === "/api/reports/inventory/low-stock")
      return send({
        items: [{ id: 1, name, current_stock: 2, min_stock_level: 5 }],
      });
    if (u.pathname === "/api/finance/cash/summary")
      return send({
        opening_balance_cents: 0,
        total_in_cents: 2990,
        total_out_cents: 0,
        net_cents: 2990,
        by_category: { sale: 2990 },
      });
    if (u.pathname === "/api/finance/cash/movements")
      return send(
        mode === "empty"
          ? []
          : [
              {
                id: 1,
                type: "in",
                category: "sale",
                description: reason,
                amount_cents: 2990,
                occurred_at: now,
              },
            ],
      );
    if (u.pathname === "/api/finance/manual-payments")
      return send({
        items: mode === "empty" ? [] : [payment],
        total: mode === "empty" ? 0 : 1,
        pending_cents: 2990,
        paid_cents: 0,
        canceled_cents: 0,
        refunded_cents: 0,
      });
    if (u.pathname === "/api/admin/users")
      return send([
        {
          id: 1,
          tenant_id: 1,
          email: "marina.operacao.restaurante.muito.longo@example.test",
          name: "Marina de Albuquerque Souza",
          role: "admin",
          active: true,
        },
      ]);
    if (u.pathname === "/api/admin/1/delivery-users")
      return send([
        {
          id: 1,
          tenant_id: 1,
          name: "Entregador de demonstração com nome completo",
          phone: "11999998888",
          active: true,
        },
      ]);
    if (u.pathname === "/api/admin/audit")
      return send([
        {
          id: 1,
          user_name: "Marina Souza",
          user_email: "marina.operacao.restaurante@example.test",
          action: "update_customer_delivery_address",
          entity_type: "customer",
          entity_id: 99,
          created_at: now,
        },
      ]);
    if (u.pathname === "/api/admin/1/whatsapp/config")
      return send({
        id: 1,
        tenant_id: 1,
        provider: "mock",
        phone_number_id: "",
        waba_id: "",
        verify_token: "",
        webhook_secret: "",
        is_enabled: false,
      });
    if (u.pathname === "/api/admin/1/whatsapp/logs")
      return send([
        {
          id: 1001,
          direction: "outgoing",
          to_phone: "5511999998888",
          from_phone: null,
          status: "delivered",
          created_at: now,
        },
      ]);
    if (u.pathname === "/api/admin/1/ai/config")
      return send({
        id: 1,
        tenant_id: 1,
        provider: "mock",
        enabled: false,
        model: "demo",
        temperature: 0.5,
        system_prompt: "Configuração de demonstração.",
      });
    if (u.pathname === "/api/admin/1/ai/logs")
      return send([
        {
          id: 1001,
          phone: "5511999998888",
          direction: "incoming",
          provider: "mock",
          error: null,
          created_at: now,
        },
      ]);
    if (u.pathname === "/api/admin/marketing/coupons")
      return send([
        {
          id: 1,
          code: "BEMVINDO_RESTAURANTE_DEMONSTRACAO_2026",
          discount_type: "percentage",
          discount_value: 10,
        },
      ]);
    if (u.pathname === "/api/admin/marketing/rewards")
      return send([{ id: 1, points_required: 200, discount_value: 12.5 }]);
    if (u.pathname === "/api/admin/billing/reviews") return send([review]);
    if (u.pathname === "/api/admin/billing/reviews/7001") return send(review);
    if (u.pathname.startsWith("/api/")) return send([]);
    if (!["localhost", "127.0.0.1"].includes(u.hostname))
      return request.abort();
    return request.continue();
  });
  return { page, errors, writes };
}
(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  try {
    for (const width of [320, 390, 768, 1366]) {
      for (const [route, count] of routes.filter(
        ([route]) =>
          !process.env.RESPONSIVE_TABLES_ROUTES ||
          process.env.RESPONSIVE_TABLES_ROUTES.split(",").includes(route),
      )) {
        const { page, errors, writes } = await fixturePage(browser, width);
        try {
          await page.goto(base + route, {
            waitUntil: "domcontentloaded",
            timeout: 60000,
          });
          await page.waitForFunction(
            (count) =>
              document.querySelectorAll("table.mobile-table-cards tbody tr")
                .length >= count,
            {},
            count,
          );
          assert.equal(
            await page.$$eval(
              "table.mobile-table-cards",
              (tables) => tables.length,
            ),
            count,
            route + " table coverage",
          );
          assert.equal(
            await page.evaluate(
              () => document.documentElement.scrollWidth > innerWidth + 1,
            ),
            false,
            route + " page overflow",
          );
          const records = await page.$$eval(
            "table.mobile-table-cards",
            (tables) =>
              tables.map((table) => ({
                display: getComputedStyle(table).display,
                role: table.getAttribute("role"),
                headers: [...table.querySelectorAll("thead th")].map((th) =>
                  th.textContent.trim(),
                ),
                cells: [
                  ...table.querySelectorAll("tbody tr:first-child td"),
                ].map((td) => ({
                  label: td.dataset.mobileLabel,
                  text: td.querySelector(".mobile-table-label")?.textContent,
                  visible: td.querySelector(".mobile-table-label")
                    ? getComputedStyle(td.querySelector(".mobile-table-label"))
                        .display
                    : null,
                  width: td.getBoundingClientRect().width,
                  role: td.getAttribute("role"),
                })),
              })),
          );
          for (const record of records) {
            assert.equal(record.role, "table");
            assert.equal(record.display, width < 1024 ? "block" : "table");
            assert.deepEqual(
              record.cells.map((c) => c.label),
              record.headers,
            );
            for (const cell of record.cells) {
              assert.equal(cell.role, "cell");
              assert.equal(cell.text, cell.label);
              assert.equal(cell.visible, width < 1024 ? "block" : "none");
            }
          }
          if (width < 1024) {
            assert.equal(
              await page.$$eval("table.mobile-table-cards", (tables) =>
                tables.some(
                  (table) => table.scrollWidth > table.clientWidth + 1,
                ),
              ),
              false,
              route + " card overflow",
            );
          }
          if (width === 390) {
            await page.$eval("table.mobile-table-cards", (table) =>
              table.scrollIntoView({ block: "center" }),
            );
            await page.screenshot({
              path: path.join(
                artifacts,
                route.replaceAll("/", "-").slice(1) + ".png",
              ),
            });
          }
          // Presentation changes must keep protected actions behind their existing flows.
          if (route === "/finance" && width === 320) {
            await page.evaluate(() =>
              [...document.querySelectorAll("button")]
                .find((b) => b.textContent === "Confirmar pagamento")
                .click(),
            );
            await page.waitForFunction(
              () =>
                document.querySelector(
                  'dialog[aria-labelledby="confirm-payment-title"]',
                )?.open,
            );
            assert.equal(writes.length, 0);
            await page.keyboard.press("Escape");
            await page.waitForFunction(
              () =>
                !document.querySelector(
                  'dialog[aria-labelledby="confirm-payment-title"]',
                )?.open,
            );
          }
          if (route === "/admin/1/delivery-users" && width === 320) {
            await page.evaluate(() =>
              [...document.querySelectorAll("button")]
                .find((b) => b.textContent.trim() === "Editar")
                .click(),
            );
            await page.waitForFunction(() =>
              document.body.innerText.includes("Editar entregador"),
            );
            await page.click('button[aria-label="Fechar modal"]');
          }
          assert.deepEqual(errors, [], route + " browser errors");
          assert.deepEqual(writes, [], route + " unintended writes");
          console.log(`PASS ${route} ${width}px (${count} tables)`);
        } catch (error) {
          console.log(
            "FAILED ROUTE",
            route,
            width,
            await page.evaluate(() =>
              [...document.querySelectorAll("body *")]
                .filter(
                  (e) =>
                    e.getBoundingClientRect().right > innerWidth + 1 &&
                    e.getBoundingClientRect().width > 0,
                )
                .slice(-12)
                .map((e) => ({
                  tag: e.tagName,
                  cls: e.className,
                  width: e.getBoundingClientRect().width,
                  text: e.innerText?.slice(0, 90),
                })),
            ),
          );
          await page.screenshot({ path: path.join(artifacts, "failed.png") });
          throw error;
        } finally {
          await page.close();
        }
      }
    }
    for (const mode of ["empty", "error"]) {
      const { page, errors, writes } = await fixturePage(browser, 320, mode);
      await page.goto(base + (mode === "empty" ? "/finance" : "/inventory"), {
        waitUntil: "domcontentloaded",
      });
      await page.waitForFunction(
        (text) => document.body.innerText.includes(text),
        {},
        mode === "empty"
          ? "Nenhum pagamento nesta situação e período."
          : "Erro ao carregar estoque.",
      );
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth + 1,
        ),
        false,
      );
      assert.deepEqual(errors, []);
      assert.deepEqual(writes, []);
      await page.close();
      console.log("PASS " + mode + " state");
    }
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
