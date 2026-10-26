const assert = require("node:assert/strict");
const { test } = require("node:test");
const ts = require("typescript");
const fs = require("node:fs");
const Module = require("node:module");
const path = require("node:path");
const filename = path.resolve(__dirname, "../lib/mobilePerformance.ts");
const code = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loaded = new Module(filename, module);
loaded.filename = filename;
loaded.paths = module.paths;
loaded._compile(code, filename);
const { mobilePerformance } = loaded.exports;
const row = (bucket, revenue, orders = 1) => ({ bucket, revenue, orders });

test("seven calendar days include zeros and ignore data outside the filter", () => {
  const { unit, buckets } = mobilePerformance(
    [row("2026-10-18", 100), row("2026-10-24", 35, 2), row("2026-10-25", 999)],
    "2026-10-18",
    "2026-10-24",
  );
  assert.equal(unit, "day");
  assert.equal(buckets.length, 7);
  assert.equal(buckets[0].start, "2026-10-18");
  assert.equal(buckets[6].end, "2026-10-24");
  assert.equal(buckets.filter((b) => b.revenueCents === 0).length, 5);
  assert.equal(
    buckets.reduce((sum, b) => sum + b.revenueCents, 0),
    13500,
  );
  assert.equal(
    buckets.reduce((sum, b) => sum + b.orders, 0),
    3,
  );
});
test("today is one daily total, never invented hourly samples", () => {
  const { buckets } = mobilePerformance(
    [row("2026-10-24", 135, 4)],
    "2026-10-24",
    "2026-10-24",
  );
  assert.deepEqual(buckets, [
    { start: "2026-10-24", end: "2026-10-24", revenueCents: 13500, orders: 4 },
  ]);
});
test("30 days preserve every day rather than sampling away low sales", () => {
  const { unit, buckets } = mobilePerformance(
    [row("2026-10-01", 0.1), row("2026-10-01", 0.2), row("2026-10-30", 50)],
    "2026-10-01",
    "2026-10-30",
  );
  assert.equal(unit, "day");
  assert.equal(buckets.length, 30);
  assert.equal(buckets[0].revenueCents, 30);
  assert.equal(buckets[29].revenueCents, 5000);
});
test("weekly aggregation clips the final week and conserves cents and orders", () => {
  const result = mobilePerformance(
    [
      row("2026-01-01", 10, 2),
      row("2026-01-07", 20, 3),
      row("2026-01-08", 30),
      row("2026-02-01", 40, 4),
    ],
    "2026-01-01",
    "2026-02-01",
  );
  assert.equal(result.unit, "week");
  assert.equal(result.buckets.length, 5);
  assert.deepEqual(result.buckets[0], {
    start: "2026-01-01",
    end: "2026-01-07",
    revenueCents: 3000,
    orders: 5,
  });
  assert.equal(result.buckets[4].end, "2026-02-01");
  assert.equal(
    result.buckets.reduce((sum, b) => sum + b.revenueCents, 0),
    10000,
  );
  assert.equal(
    result.buckets.reduce((sum, b) => sum + b.orders, 0),
    10,
  );
});
test("monthly groups include only selected parts of the first and last month", () => {
  const { unit, buckets } = mobilePerformance(
    [
      row("2025-12-31", 99),
      row("2026-01-01", 99),
      row("2026-01-15", 10),
      row("2026-08-10", 20),
      row("2026-08-11", 99),
    ],
    "2026-01-15",
    "2026-08-10",
  );
  assert.equal(unit, "month");
  assert.equal(buckets.length, 8);
  assert.equal(buckets[0].start, "2026-01-15");
  assert.equal(buckets[7].end, "2026-08-10");
  assert.equal(
    buckets.reduce((sum, b) => sum + b.revenueCents, 0),
    3000,
  );
});
test("invalid ranges do not produce chart data; leap day remains a calendar day", () => {
  assert.equal(
    mobilePerformance([], "2026-02-30", "2026-03-01").buckets.length,
    0,
  );
  assert.equal(
    mobilePerformance([], "2026-03-02", "2026-03-01").buckets.length,
    0,
  );
  assert.equal(
    mobilePerformance([], "2024-02-28", "2024-03-01").buckets.length,
    3,
  );
});
