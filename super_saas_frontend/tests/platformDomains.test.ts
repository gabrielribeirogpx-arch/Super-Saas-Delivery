import assert from "node:assert/strict";
import test from "node:test";

import {
  buildTenantPublicUrl,
  extractPlatformTenantSlug,
  getCanonicalPublicBaseDomain,
} from "../lib/platformDomains.ts";

test("uses Fomizero for every newly generated tenant URL", () => {
  assert.equal(getCanonicalPublicBaseDomain(), "fomizero.com.br");
  assert.equal(buildTenantPublicUrl("tempero"), "https://tempero.fomizero.com.br");
  assert.equal(
    buildTenantPublicUrl("tempero", "/login"),
    "https://tempero.fomizero.com.br/login"
  );
  assert.ok(!buildTenantPublicUrl("tempero").includes("servicedelivery.com.br"));
});

test("resolves tenant slugs on canonical and temporary legacy hosts", () => {
  assert.equal(extractPlatformTenantSlug("tempero.fomizero.com.br"), "tempero");
  assert.equal(extractPlatformTenantSlug("tempero.servicedelivery.com.br"), "tempero");
});
