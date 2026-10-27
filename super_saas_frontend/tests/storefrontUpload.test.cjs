const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");

test("same-origin storefront uploads are routed to the backend legacy endpoint", async () => {
  const config = (await import("../next.config.mjs?storefront-upload-test")).default;
  const routes = await config.rewrites();
  const upload = routes.find((route) => route.source === "/storefront/upload");
  assert.ok(upload);
  assert.match(upload.destination, /\/storefront\/upload$/);
});

test("storefront upload sends multipart data and reports the failing step", async () => {
  let response = new Response(JSON.stringify({ url: "https://cdn.example.com/logo.png" }), { status: 200 });
  let requestedUrl = "";
  let requestedBody;
  const context = {
    exports: {}, FormData, Response, URLSearchParams,
    require: (name) => name === "@/lib/api" ? {
      apiFetch: async (url, options) => { requestedUrl = url; requestedBody = options.body; return response; },
    } : require(name),
  };
  const source = fs.readFileSync("lib/storefrontUpload.ts", "utf8");
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, context);
  const file = new File(["test"], "logo.png", { type: "image/png" });

  assert.equal(await context.exports.uploadStorefrontAsset(file, 7, "logo"), "https://cdn.example.com/logo.png");
  assert.equal(requestedUrl, "/storefront/upload?tenant_id=7&category=storefront&subfolder=logo");
  assert.equal(requestedBody.get("file").name, "logo.png");

  response = new Response(JSON.stringify({ detail: "A logo excede o limite de 1 MB." }), { status: 413 });
  await assert.rejects(() => context.exports.uploadStorefrontAsset(file, 7, "logo"), /A logo excede o limite/);
  response = new Response("<html>not found</html>", { status: 404 });
  await assert.rejects(() => context.exports.uploadStorefrontAsset(file, 7, "logo"), /envio da logo está indisponível/);
});
