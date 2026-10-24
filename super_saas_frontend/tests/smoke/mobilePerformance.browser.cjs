// Local API fixtures only; no live data, messages or payments.
const puppeteer = require("puppeteer-core");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const base =
  process.env.MOBILE_PERFORMANCE_TEST_BASE_URL || "http://127.0.0.1:3046";
const artifacts =
  process.env.MOBILE_PERFORMANCE_ARTIFACT_DIR ||
  path.join(os.tmpdir(), "fomizero-mobile-performance");
fs.mkdirSync(artifacts, { recursive: true });
(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  try {
    for (const width of [320, 390, 768, 1366]) {
      const page = await browser.newPage();
      const errors = [],
        queries = [];
      let unavailable = false;
      await page.setViewport({ width, height: 844 });
      await page.setBypassServiceWorker(true);
      await page.evaluateOnNewDocument(() => {
        delete Navigator.prototype.serviceWorker;
      });
      page.on("pageerror", (error) => errors.push(error.message));
      await page.setRequestInterception(true);
      page.on("request", (request) => {
        const url = new URL(request.url());
        const send = (data, status = 200) =>
          request.respond({
            status,
            contentType: "application/json",
            body: JSON.stringify(data),
          });
        if (url.pathname === "/api/admin/auth/me")
          return send({
            id: 1,
            tenant_id: 1,
            name: "Marina",
            role: "owner",
            active: true,
          });
        if (url.pathname === "/api/admin/billing/access")
          return send({ managed: false, active: true, features: {} });
        if (url.pathname === "/api/dashboard/overview")
          return send({
            total_orders: 3,
            total_revenue: 135,
            average_ticket: 45,
            active_customers: 2,
          });
        if (url.pathname === "/api/dashboard/timeseries") {
          const start = url.searchParams.get("start_date"),
            end = url.searchParams.get("end_date");
          queries.push({ start, end });
          if (unavailable)
            return send({ detail: "Synthetic unavailable series" }, 503);
          const points = [];
          for (
            let day = Date.parse(start + "T00:00:00Z");
            day <= Date.parse(end + "T00:00:00Z");
            day += 86400000
          ) {
            const date = new Date(day).toISOString().slice(0, 10);
            points.push({
              date,
              gross_sales_cents:
                start === end
                  ? 13500
                  : date === start
                    ? 10000
                    : date === end
                      ? 3500
                      : 0,
              orders_count:
                start === end ? 3 : date === start ? 1 : date === end ? 2 : 0,
            });
          }
          return send({ points });
        }
        if (url.pathname.startsWith("/api/")) return send([]);
        if (!["127.0.0.1", "localhost"].includes(url.hostname))
          return request.abort();
        return request.continue();
      });
      const section = 'section[aria-label="Gráfico de vendas no celular"]';
      const buttons = section + ' [role="group"] button';
      const noOverflow = async () =>
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth + 1,
          ),
          false,
        );
      await page.goto(base + "/dashboard", { waitUntil: "domcontentloaded" });
      await page.waitForSelector(buttons);
      if (width >= 1024) {
        assert.equal(
          await page.$eval(section, (e) => e.getBoundingClientRect().height),
          0,
        );
        assert.equal(
          await page.$$eval(
            ".recharts-line",
            (nodes) =>
              nodes.filter((n) => n.getBoundingClientRect().width > 0).length,
          ),
          1,
        );
        await noOverflow();
        assert.deepEqual(errors, []);
        console.log("PASS desktop keeps original line chart");
        await page.close();
        continue;
      }
      assert.equal(await page.$$eval(buttons, (nodes) => nodes.length), 7);
      assert.match(await page.$eval(section, (e) => e.textContent), /135,00/);
      await noOverflow();
      const first = await page.$(buttons);
      await first.click();
      await page.waitForFunction(
        (selector) =>
          document.querySelector(selector).getAttribute("aria-pressed") ===
          "true",
        {},
        buttons,
      );
      assert.match(
        await page.$eval(section + " [aria-live]", (e) => e.textContent),
        /100,00/,
      );
      await page.$eval(section, (e) => e.scrollIntoView({ block: "center" }));
      await page.screenshot({
        path: path.join(artifacts, `mobile-chart-week-${width}.png`),
      });
      const preset = 'select[aria-label="Selecionar período do dashboard"]';
      await page.select(preset, "today");
      await page.waitForFunction(
        (selector) => document.querySelectorAll(selector).length === 1,
        {},
        buttons,
      );
      assert.match(
        await page.$eval(buttons, (e) => e.getAttribute("aria-label")),
        /135,00/,
      );
      await page.select(preset, "last30");
      await page.waitForFunction(
        (selector) => document.querySelectorAll(selector).length === 30,
        {},
        buttons,
      );
      assert.equal(
        await page.$eval(
          section + ' [role="group"]',
          (e) => e.scrollWidth > e.clientWidth,
        ),
        true,
      );
      assert.match(await page.$eval(section, (e) => e.textContent), /Deslize/);
      await page.select(preset, "custom");
      const setDate = async (label, value) => {
        const selector = `input[aria-label="${label}"]`;
        await page.waitForSelector(selector);
        await page.$eval(
          selector,
          (input, value) => {
            Object.getOwnPropertyDescriptor(
              HTMLInputElement.prototype,
              "value",
            ).set.call(input, value);
            input.dispatchEvent(new Event("input", { bubbles: true }));
          },
          value,
        );
      };
      await setDate("Data inicial", "2026-01-01");
      await setDate("Data final", "2026-02-01");
      await page.waitForFunction(
        (selector) =>
          document.querySelector(selector)?.dataset.bucketUnit === "week" &&
          document.querySelectorAll(selector + ' [role="group"] button')
            .length === 5,
        {},
        section,
      );
      assert.match(await page.$eval(section, (e) => e.textContent), /135,00/);
      await setDate("Data final", "2026-08-01");
      await page.waitForFunction(
        (selector) =>
          document.querySelector(selector)?.dataset.bucketUnit === "month",
        {},
        section,
      );
      assert.match(await page.$eval(section, (e) => e.textContent), /135,00/);
      await noOverflow();
      unavailable = true;
      await setDate("Data final", "2026-08-02");
      await page.waitForFunction(
        (selector) =>
          document
            .querySelector(selector)
            ?.textContent.includes("Distribuição diária indisponível"),
        {},
        section,
      );
      assert.equal(
        await page.$$eval(buttons, (nodes) => nodes.length),
        0,
        "Unavailable series must never invent an overview-based daily bar",
      );
      assert.deepEqual(errors, []);
      assert(
        queries.some((q) => q.start === "2026-01-01" && q.end === "2026-02-01"),
      );
      console.log(
        `PASS mobile period fidelity, touch, daily/weekly/monthly totals and unavailable series at ${width}px`,
      );
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
