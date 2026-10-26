import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { BillingReviewEvidence } from "../components/admin/BillingReviewEvidence.ts";
import { canReviewBilling, reviewCanApprove, reviewReason } from "../lib/billingReviews.ts";
import type { BillingReview } from "../lib/billingReviews.ts";

function review(changes: Partial<BillingReview> = {}): BillingReview {
  return { billing_event_id: 7, provider: "kiwify", event_type: "order_approved", order_id: "sale-reference",
    external_subscription_id: "subscription-reference", product_id: "product-reference", external_offer_id: "offer-reference",
    candidate_plan_id: 1, candidate_plan_name: "Essencial", candidate_tenant_id: 1, verification_status: "manual_review",
    received_at: "2026-10-07T12:00:00Z", occurred_at: null, sale_checked_at: "2026-10-07T12:00:00Z",
    sale_status: "paid", period_start: null, period_end: null, reason: "sale_confirmed_subscription_unconfirmed",
    can_approve: true, access_pending_period: true, approval_blockers: [], decision: null,
    decided_by: null, decided_at: null, rejection_reason: null, ...changes };
}

test("evidence view exposes allowlisted fields without arbitrary payload properties", () => {
  const value = { ...review(), payload: { email: "PRIVATE_MARKER" }, token: "PRIVATE_MARKER", signature: "PRIVATE_MARKER" };
  const html = renderToStaticMarkup(createElement(BillingReviewEvidence, { review: value }));
  assert.ok(html.includes("sale-reference"));
  assert.ok(html.includes("Essencial"));
  assert.ok(!html.includes("PRIVATE_MARKER"));
});

test("billing review navigation is restricted to tenant administrators and owners", () => {
  assert.ok(canReviewBilling("admin"));
  assert.ok(canReviewBilling(" OWNER "));
  for (const role of ["operator", "cashier", "delivery", undefined]) assert.ok(!canReviewBilling(role));
});

test("approval follows server eligibility and refuses pending mutation or an existing decision", () => {
  assert.ok(reviewCanApprove(review(), false)); // Binding-only approval is available without a period.
  assert.ok(!reviewCanApprove(review(), true));
  assert.ok(!reviewCanApprove(review({ can_approve: false }), false));
  assert.ok(!reviewCanApprove(review({ decision: "binding_approved" }), false));
  assert.ok(!reviewCanApprove(review({ verification_status: "verified" }), false));
});

test("binding approval clearly leaves access pending and never displays unknown exception content", () => {
  assert.match(reviewReason("manual_review_period_missing"), /Vínculo validado/);
  assert.match(reviewReason("manual_review_period_missing"), /acesso continua pendente/);
  assert.ok(!reviewReason("PRIVATE_MARKER").includes("PRIVATE_MARKER"));
});
