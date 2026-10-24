// Browser-only fixtures; no live API, charges or messages.
const puppeteer = require("puppeteer-core");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const artifacts =
  process.env.MOBILE_ADMIN_ARTIFACT_DIR ||
  path.join(os.tmpdir(), "fomizero-mobile-admin");
fs.mkdirSync(artifacts, { recursive: true });
const base = process.env.MOBILE_ADMIN_TEST_BASE_URL || "http://127.0.0.1:3046";
const orders = [1, 2, 3].map((id) => ({
  id,
  tenant_id: 1,
  daily_order_number: id,
  cliente_nome: `Cliente de teste ${id}`,
  cliente_telefone: "11999999999",
  tipo_entrega: "RETIRADA",
  forma_pagamento: "DINHEIRO",
  status: ["RECEBIDO", "EM_PREPARO", "PRONTO"][id - 1],
  total_cents: 4500,
  valor_total: 4500,
  created_at: new Date().toISOString(),
  items: [
    {
      id,
      name: "Hambúrguer artesanal",
      quantity: 2,
      unit_price_cents: 2250,
      subtotal_cents: 4500,
      production_area: "COZINHA",
    },
  ],
}));
(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  try {
    for (const { width, role } of [320, 390, 768, 1366, 1720]
      .map((width) => ({ width, role: "owner" }))
      .concat([{ width: 390, role: "delivery" }])) {
      const page = await browser.newPage();
      const errors = [],
        writes = [];
      await page.setViewport({
        width,
        height: 844,
        isMobile: width < 768,
        hasTouch: width < 1024,
      });
      await page.setBypassServiceWorker(true);
      await page.evaluateOnNewDocument(() => {
        delete Navigator.prototype.serviceWorker;
      });
      page.on("pageerror", (error) => errors.push(error.message));
      await page.setRequestInterception(true);
      page.on("request", (request) => {
        const url = new URL(request.url());
        const send = (data) =>
          request.respond({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(data),
          });
        if (url.pathname === "/api/admin/auth/me")
          return send({
            id: 1,
            tenant_id: 1,
            name: "Marina Souza",
            role,
            active: true,
          });
        if (url.pathname === "/api/admin/billing/access")
          return send({ managed: false, active: true, features: {} });
        if (url.pathname === "/api/dashboard/overview")
          return send({
            total_orders: 24,
            total_revenue: 1490.5,
            average_ticket: 62.1,
            active_customers: 18,
          });
        if (url.pathname === "/api/dashboard/timeseries")
          return send([
            { bucket: "2026-10-23", revenue: 850, orders: 12 },
            { bucket: "2026-10-24", revenue: 1490.5, orders: 24 },
          ]);
        if (url.pathname === "/api/dashboard/top-items")
          return send([
            { name: "Hambúrguer artesanal", quantity: 18, revenue: 810 },
          ]);
        if (url.pathname === "/api/dashboard/recent-orders")
          return send(orders.map((o) => ({ ...o, total: 45 })));
        if (url.pathname === "/api/orders/1/overview")
          return send({
            total: 3,
            summary: {
              today: 3,
              pending: 1,
              preparing: 1,
              delivering: 0,
              completed: 0,
            },
            payments: ["DINHEIRO"],
            deliveries: ["RETIRADA"],
          });
        if (url.pathname === "/api/orders/1/search")
          return send({ items: orders, total: 3, page: 1, page_size: 8 });
        if (/\/api\/orders\/\d+\/items/.test(url.pathname))
          return send(orders[0].items);
        if (url.pathname === "/api/kds/orders") return send(orders);
        if (url.pathname.startsWith("/api/")) {
          if (request.method() !== "GET") writes.push(url.pathname);
          return send([]);
        }
        if (!["127.0.0.1", "localhost"].includes(url.hostname))
          return request.abort();
        return request.continue();
      });
      const noOverflow = async () =>
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth + 1,
          ),
          false,
          "Page must fit viewport",
        );
      await page.goto(base + "/dashboard", { waitUntil: "domcontentloaded" });
      if (role === "delivery") {
        await page.waitForSelector(".admin-bottom-nav");
        assert.equal(
          await page.$$eval(".admin-bottom-nav a", (links) => links.length),
          1,
        );
        assert.equal(
          await page.$eval(".admin-bottom-nav a", (link) =>
            link.getAttribute("href"),
          ),
          "/admin/1/delivery",
        );
        await page.click('button[aria-label="Abrir menu"]');
        await page.waitForFunction(() => document.querySelector("dialog").open);
        const links = await page.$$eval("dialog nav a", (links) =>
          links.map((link) => link.getAttribute("href")),
        );
        assert.deepEqual(links, ["/admin/1/delivery"]);
        await page.keyboard.press("Escape");
        assert.deepEqual(errors, []);
        console.log("PASS delivery role navigation isolation");
        await page.close();
        continue;
      }
      await page.waitForSelector(".admin-dashboard-stats");
      assert.match(await page.title(), /Fomizero/);
      assert.equal(
        await page.$('link[rel="manifest"]'),
        null,
        "Restaurant panel must not advertise the driver/customer PWA",
      );
      assert.equal(
        await page.$("details summary"),
        null,
        "Driver diagnostics must not cover restaurant navigation",
      );
      await page.select(
        'select[aria-label="Selecionar período do dashboard"]',
        "custom",
      );
      await noOverflow();
      await page.select(
        'select[aria-label="Selecionar período do dashboard"]',
        "last7",
      );
      await noOverflow();
      if (width < 1024) {
        await page.screenshot({
          path: `${artifacts}/mobile-admin-home-${width}.png`,
          fullPage: true,
        });
        assert.equal(
          await page.$eval('.admin-bottom-nav a[href="/dashboard"]', (e) =>
            e.getAttribute("aria-current"),
          ),
          "page",
        );
        await page.click('button[aria-label="Abrir menu"]');
        await page.waitForFunction(() => document.querySelector("dialog").open);
        assert.equal(
          await page.evaluate(() => document.body.style.overflow),
          "hidden",
        );
        for (let i = 0; i < 8; i++) {
          await page.keyboard.press("Tab");
          assert.equal(
            await page.evaluate(() =>
              Boolean(document.activeElement.closest("dialog")),
            ),
            true,
          );
        }
        // Native dialog traps tab navigation and Escape restores the trigger.
        await page.keyboard.press("Escape");
        await page.waitForFunction(
          () => !document.querySelector("dialog").open,
        );
        assert.equal(
          await page.evaluate(() =>
            document.activeElement.getAttribute("aria-label"),
          ),
          "Abrir menu",
        );
        await page.evaluate(() => {
          Object.defineProperty(navigator, "onLine", {
            configurable: true,
            get: () => false,
          });
          window.dispatchEvent(new Event("offline"));
        });
        await page.waitForFunction(() =>
          document.body.innerText.includes("Sem conexão."),
        );
        await page.evaluate(() => {
          Object.defineProperty(navigator, "onLine", {
            configurable: true,
            get: () => true,
          });
          window.dispatchEvent(new Event("online"));
        });
        await page.waitForFunction(
          () => !document.body.innerText.includes("Sem conexão."),
        );
        await page.click('.admin-bottom-nav a[href="/orders"]');
      } else {
        assert.equal(
          await page.$eval(
            ".admin-bottom-nav",
            (e) => getComputedStyle(e).display,
          ),
          "none",
        );
        await page.goto(base + "/orders", { waitUntil: "domcontentloaded" });
      }
      try {
        await page.waitForSelector(".admin-summary-strip");
      } catch (e) {
        console.log(
          "FAIL PAGE",
          page.url(),
          await page.evaluate(() => document.body.innerText.slice(-1500)),
        );
        await page.screenshot({
          path: path.join(artifacts, "mobile-admin-failed.png"),
        });
        throw e;
      }
      await noOverflow();
      if (width >= 1024)
        assert.equal(
          await page.$eval(".admin-orders-filters", (el) => el.open),
          true,
        );
      if (width < 1024) await page.click('button[aria-label="Abrir menu"]');
      if (width < 1024) {
        await page.waitForFunction(() => document.querySelector("dialog").open);
        await page.screenshot({
          path: `${artifacts}/mobile-admin-menu-${width}.png`,
        });
        await page.keyboard.press("Escape");
        // All primary controls are touch sized and the menu restores focus.
        assert(
          await page.$$eval(
            ".admin-bottom-nav a, .admin-bottom-nav button",
            (nodes) =>
              nodes.every((node) => node.getBoundingClientRect().height >= 44),
          ),
        );
      }
      if (width < 1024)
        await page.evaluate(() =>
          [...document.querySelectorAll("button")]
            .find(
              (b) =>
                b.textContent === "Detalhes" &&
                b.getBoundingClientRect().height > 0,
            )
            .click(),
        );
      else await page.click("tbody tr");
      if (width < 1680) {
        await page.waitForFunction(
          () =>
            document.querySelector('dialog[aria-label="Detalhes do pedido"]')
              ?.open,
        );
        assert.equal(
          await page.evaluate(() => document.body.style.overflow),
          "hidden",
        );
        await page.screenshot({
          path: `${artifacts}/mobile-admin-detail-${width}.png`,
        });
        await page.keyboard.press("Escape");
        await page.waitForFunction(
          () =>
            !document.querySelector('dialog[aria-label="Detalhes do pedido"]'),
        );
      } else
        assert.equal(
          await page.$$eval("dialog[open]", (nodes) => nodes.length),
          0,
        );
      if (width < 1024) {
        await page.screenshot({
          path: `${artifacts}/mobile-admin-orders-${width}.png`,
          fullPage: true,
        });
        await page.click(".admin-orders-filters > summary");
        await page.waitForFunction(
          () => document.querySelector(".admin-orders-filters").open,
        );
        await page.type('input[placeholder="Buscar cliente"]', "Cliente");
        await page.click(".admin-orders-filters > summary");
        await page.click('.admin-bottom-nav a[href="/kds"]');
      } else await page.goto(base + "/kds", { waitUntil: "domcontentloaded" });
      await page.waitForSelector('nav[aria-label="Etapas da cozinha"]');
      if (width < 1280) {
        const tabs = await page.$$(
          'nav[aria-label="Etapas da cozinha"] button',
        );
        await tabs[1].click();
        assert.equal(
          await tabs[1].evaluate((e) => e.getAttribute("aria-pressed")),
          "true",
        );
        await page.screenshot({
          path: `${artifacts}/mobile-admin-kitchen-${width}.png`,
          fullPage: true,
        });
      }
      await noOverflow();
      assert.deepEqual(errors, []);
      assert.deepEqual(writes, []);
      console.log(`PASS restaurant mobile navigation at ${width}px`);
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
