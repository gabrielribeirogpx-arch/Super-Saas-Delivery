const assert = require("node:assert/strict");
const puppeteer = require("puppeteer-core");

const base = process.env.KDS_MOTION_TEST_BASE_URL || "http://127.0.0.1:3181";

(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1365, height: 768 });
    await page.setBypassServiceWorker(true);
    await page.evaluateOnNewDocument(() => { delete Navigator.prototype.serviceWorker; });
    let status = "pending";
    await page.setRequestInterception(true);
    page.on("request", (request) => {
      const url = new URL(request.url());
      const respond = (data) => request.respond({ status: 200, contentType: "application/json", body: JSON.stringify(data) });
      if (url.pathname === "/api/admin/auth/me") return respond({ id: 1, tenant_id: 1, name: "Teste", role: "owner", active: true });
      if (url.pathname === "/api/admin/billing/access") return respond({ managed: false, active: true, features: {} });
      if (url.pathname === "/api/kds/orders/1/start" && request.method() === "POST") {
        return setTimeout(() => { status = "preparing"; respond({ ok: true, status }); }, 450);
      }
      if (url.pathname === "/api/kds/orders/1/ready" && request.method() === "POST") {
        return setTimeout(() => { status = "PRONTO"; respond({ ok: true, status, ready_areas: ["COZINHA"] }); }, 450);
      }
      if (url.pathname === "/api/kds/orders") return respond([{
        id: 1, tenant_id: 1, daily_order_number: 7, status,
        created_at: new Date().toISOString(), cliente_nome: "Maria", total: 29.9,
        ready_areas: status === "PRONTO" ? ["COZINHA"] : [],
        itens: [{ id: 1, name: "Hambúrguer", quantity: 1, production_area: "COZINHA" }],
      }]);
      if (url.pathname.startsWith("/api/")) return respond([]);
      if (!["127.0.0.1", "localhost"].includes(url.hostname)) return request.abort();
      return request.continue();
    });

    await page.goto(`${base}/kds`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector('[data-kds-order-id="1"][data-kds-stage="pending"]');
    await page.click('[data-kds-stage="pending"] button:not([disabled])');
    await page.waitForSelector('[data-kds-order-id="1"].kds-order-card-advancing');
    await page.waitForSelector('[data-kds-order-id="1"][data-kds-stage="preparing"]');
    assert.equal(await page.$eval('[data-kds-stage="preparing"]', (card) => getComputedStyle(card).animationName), "kds-card-arrive");

    await page.click('[data-kds-stage="preparing"] button:not([disabled])');
    await page.waitForSelector('[data-kds-order-id="1"][data-kds-stage="ready"]');
    assert.equal(await page.$eval('[data-kds-stage="ready"]', (card) => getComputedStyle(card).animationName), "kds-card-arrive");

    await page.emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "reduce" }]);
    assert.equal(await page.$eval('[data-kds-stage="ready"]', (card) => getComputedStyle(card).animationName), "none");
    console.log("PASS KDS card motion through preparation and ready, with reduced motion");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
