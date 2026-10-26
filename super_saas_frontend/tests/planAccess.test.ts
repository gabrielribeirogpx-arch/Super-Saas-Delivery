import assert from "node:assert/strict";
import test from "node:test";
import { routeFeature, featureBlocked } from "../lib/planAccess.ts";

test("feature pages and nested routes map to commercial access", () => {
  for (const [path,feature] of [["/inventory/items","inventory"],["/reports","advanced_reports"],["/whatsapp","whatsapp"],
    ["/marketing/coupons","coupons"],["/marketing/rewards","loyalty"],["/admin/7/map","tracking"]]) {
    assert.equal(routeFeature(path),feature);
  }
});
test("recovery, history and account management stay reachable", () => {
  for (const path of ["/subscriptions","/finance","/orders","/users","/admin/7/delivery-users","/reports-other"]) {
    assert.equal(routeFeature(path),undefined);
  }
});
test("managed access fails closed for unavailable feature; legacy is not migrated", () => {
  assert(featureBlocked({managed:true,active:true,features:{}},"inventory"));
  assert(!featureBlocked({managed:false,active:true,features:{}},"inventory"));
  assert(!featureBlocked({managed:true,active:false,features:{}},undefined));
});
