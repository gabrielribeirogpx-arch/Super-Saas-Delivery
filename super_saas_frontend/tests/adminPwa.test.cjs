const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const publicDir = path.join(__dirname, "..", "public");

test("restaurant PWA has its own identity and opens the admin dashboard", () => {
  const admin = JSON.parse(fs.readFileSync(path.join(publicDir, "admin-manifest.webmanifest"), "utf8"));
  const driver = JSON.parse(fs.readFileSync(path.join(publicDir, "manifest.webmanifest"), "utf8"));
  assert.equal(admin.start_url, "/dashboard");
  assert.equal(admin.display, "standalone");
  assert.notEqual(admin.id, driver.id);
  assert.equal(admin.theme_color, "#dc2626");
});

test("shared PWA worker fetches admin pages without writing them to cache", async () => {
  const handlers = {};
  const fetched = [];
  const context = {
    self: {
      location: { hostname: "example.com", origin: "https://example.com" },
      addEventListener(name, handler) { handlers[name] = handler; },
    },
    caches: { open() { throw new Error("Admin data must not use CacheStorage"); } },
    fetch(request) { fetched.push(request.url); return Promise.resolve({ ok: true }); },
    URL,
  };
  vm.runInNewContext(fs.readFileSync(path.join(publicDir, "customer-sw.js"), "utf8"), context);
  for (const route of ["/dashboard", "/install-app", "/api/admin/auth/me"]) {
    let response;
    handlers.fetch({
      request: { url: `https://example.com${route}`, method: "GET", mode: "navigate", destination: "document" },
      respondWith(value) { response = value; },
    });
    assert.ok(response, `${route} should be handled`);
    assert.equal((await response).ok, true);
  }
  assert.deepEqual(fetched, [
    "https://example.com/dashboard",
    "https://example.com/install-app",
    "https://example.com/api/admin/auth/me",
  ]);
});
