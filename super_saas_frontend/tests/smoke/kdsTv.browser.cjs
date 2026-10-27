const assert = require("node:assert/strict");
const puppeteer = require("puppeteer-core");

const base = process.env.KDS_TV_TEST_BASE_URL || "http://127.0.0.1:3180";

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
    await page.evaluateOnNewDocument(() => {
      delete Navigator.prototype.serviceWorker;
      Element.prototype.requestFullscreen = () => Promise.reject(new DOMException("Fullscreen denied", "NotAllowedError"));
    });
    await page.setRequestInterception(true);
    page.on("request", (request) => {
      const url = new URL(request.url());
      const respond = (data) => request.respond({ status: 200, contentType: "application/json", body: JSON.stringify(data) });
      if (url.pathname === "/api/admin/auth/me") return respond({ id: 1, tenant_id: 1, name: "Teste", role: "owner", active: true });
      if (url.pathname === "/api/admin/billing/access") return respond({ managed: false, active: true, features: {} });
      if (url.pathname === "/api/kds/orders") return respond([]);
      if (url.pathname.startsWith("/api/")) return respond([]);
      if (!["127.0.0.1", "localhost"].includes(url.hostname)) return request.abort();
      return request.continue();
    });

    await page.goto(`${base}/kds`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => [...document.querySelectorAll("button")].some((button) => button.textContent.includes("Modo TV")));
    assert.equal(await page.$('aside[aria-live="polite"]'), null, "Invisible order toast must not cover TV controls");
    await page.evaluate(() => [...document.querySelectorAll("button")].find((button) => button.textContent.includes("Modo TV")).setAttribute("data-tv-button", ""));
    await page.click("[data-tv-button]");
    await page.waitForSelector(".tv-mode");
    await new Promise((resolve) => setTimeout(resolve, 500));
    assert.deepEqual(await page.$eval(".tv-mode", (element) => {
      const bounds = element.getBoundingClientRect();
      return { x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height };
    }), { x: 0, y: 0, width: 1365, height: 768 });
    assert.equal(await page.$eval("aside", (element) => getComputedStyle(element).display), "none");

    await page.click("[data-tv-button]");
    await page.waitForFunction(() => !document.querySelector(".tv-mode"));
    assert.notEqual(await page.$eval("aside", (element) => getComputedStyle(element).display), "none");

    await page.click("[data-tv-button]");
    await page.waitForSelector(".tv-mode");
    await new Promise((resolve) => setTimeout(resolve, 500));
    await page.keyboard.press("Escape");
    await page.waitForFunction(() => !document.querySelector(".tv-mode"));
    console.log("PASS KDS TV fallback, exit button and Escape");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
