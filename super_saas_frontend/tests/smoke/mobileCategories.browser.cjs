const assert = require("node:assert/strict");
const puppeteer = require("puppeteer-core");

const base = process.env.MOBILE_CATEGORIES_TEST_BASE_URL || "http://127.0.0.1:3179";
const categories = [{ id: 1, tenant_id: 1, name: "Burgers", sort_order: 0, active: true }];
const writes = [];

(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
    await page.setBypassServiceWorker(true);
    await page.evaluateOnNewDocument(() => { delete Navigator.prototype.serviceWorker; });
    page.on("dialog", (dialog) => dialog.accept());
    await page.setRequestInterception(true);
    page.on("request", (request) => {
      const url = new URL(request.url());
      const respond = (data) => request.respond({ status: 200, contentType: "application/json", body: JSON.stringify(data) });
      if (url.pathname === "/api/admin/auth/me") return respond({ id: 1, tenant_id: 1, name: "Teste", role: "owner", active: true });
      if (url.pathname === "/api/admin/billing/access") return respond({ managed: false, active: true, features: {} });
      if (url.pathname === "/api/admin/menu/items") return respond([]);
      if (url.pathname === "/api/admin/menu/categories") {
        if (request.method() === "POST") {
          const payload = JSON.parse(request.postData());
          writes.push({ method: "POST", payload });
          const category = { ...payload, id: categories.length + 1 };
          categories.push(category);
          return respond(category);
        }
        return respond(categories);
      }
      if (url.pathname.startsWith("/api/admin/menu/categories/") && request.method() === "PUT") {
        const payload = JSON.parse(request.postData());
        writes.push({ method: "PUT", payload });
        const category = categories.find((entry) => entry.id === Number(url.pathname.split("/").pop()));
        Object.assign(category, payload);
        return respond(category);
      }
      if (url.pathname.startsWith("/api/")) return respond([]);
      if (!["127.0.0.1", "localhost"].includes(url.hostname)) return request.abort();
      return request.continue();
    });

    await page.goto(`${base}/menu`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => [...document.querySelectorAll('button')].some((button) => button.textContent === 'Categorias'));
    await page.evaluate(() => [...document.querySelectorAll('button')].find((button) => button.textContent === 'Categorias').click());
    await page.waitForSelector('button:not([hidden])');
    assert.equal(await page.$('[role="dialog"][aria-labelledby="mobile-category-editor-title"]'), null);
    await page.click('button[class*="fixed"][class*="lg:hidden"]');
    await page.waitForSelector('#mobile-category-name');
    assert.equal(await page.$eval('#mobile-category-order', (input) => input.value), "1");
    await page.click('[role="dialog"] button[type="submit"]');
    await page.waitForSelector('#mobile-category-name-error');
    assert.equal(writes.length, 0, "Name is required");
    await page.type('#mobile-category-name', 'Bebidas');
    await page.click('[role="dialog"] button[type="submit"]');
    await page.waitForFunction(() => !document.querySelector('[role="dialog"][aria-labelledby="mobile-category-editor-title"]'));
    assert.deepEqual(writes[0], { method: "POST", payload: { tenant_id: 1, name: "Bebidas", sort_order: 1, active: true } });

    await page.waitForSelector('button[aria-label="Editar categoria Bebidas"]');
    await page.click('button[aria-label="Editar categoria Bebidas"]');
    await page.waitForSelector('#mobile-category-name');
    await page.click('#mobile-category-name');
    await page.keyboard.down('Control');
    await page.keyboard.press('KeyA');
    await page.keyboard.up('Control');
    await page.type('#mobile-category-name', 'Bebidas geladas');
    await page.click('[role="dialog"] button[type="submit"]');
    await page.waitForFunction(() => !document.querySelector('[role="dialog"][aria-labelledby="mobile-category-editor-title"]'));
    assert.deepEqual(writes[1], { method: "PUT", payload: { name: "Bebidas geladas", sort_order: 1, active: true } });

    await page.waitForSelector('button[aria-label="Editar categoria Bebidas geladas"]');
    await page.click('button[aria-label="Editar categoria Bebidas geladas"]');
    await page.type('#mobile-category-name', ' extra');
    await page.click('button[aria-label="Fechar formulário de categoria"]');
    assert.equal(writes.length, 2, "Discard does not save");
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    console.log("PASS mobile category create, validation, edit, discard and auto order");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
