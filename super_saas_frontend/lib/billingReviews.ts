export interface BillingReview {
  billing_event_id: number;
  provider: string;
  event_type: string;
  order_id: string | null;
  external_subscription_id: string | null;
  product_id: string | null;
  external_offer_id: string | null;
  candidate_plan_id: number | null;
  candidate_plan_name: string | null;
  candidate_tenant_id: number | null;
  verification_status: string;
  received_at: string;
  occurred_at: string | null;
  sale_checked_at: string | null;
  sale_status: string | null;
  period_start: string | null;
  period_end: string | null;
  reason: string;
  can_approve: boolean;
  access_pending_period: boolean;
  approval_blockers: string[];
  decision: string | null;
  decided_by: number | null;
  decided_at: string | null;
  rejection_reason: string | null;
}

export const reviewNotice = "Venda confirmada pela Kiwify, mas vínculo/período da assinatura exige aprovação administrativa.";

export const reviewReasons: Record<string, string> = {
  trusted_period_missing: "Período confiável da assinatura ausente. Aprovação indisponível.",
  manual_review_period_missing: "Vínculo validado. O acesso continua pendente por ausência de período confiável.",
  existing_subscription_binding_mismatch: "Já existe uma assinatura com vínculo incompatível.",
  existing_subscription_requires_trusted_period: "A assinatura existente exige um período confiável para esta decisão.",
  trusted_tenant_missing: "Tenant não identificado por correlação interna confiável.",
  internal_plan_missing_or_mismatched: "Plano interno ausente ou incompatível com a intenção interna.",
  confirmed_paid_sale_missing: "Falta evidência de venda paga confirmada pela API oficial.",
  sale_evidence_stale_or_missing: "Evidência da venda ausente ou com mais de cinco minutos.",
  event_not_pending_review: "Este evento já recebeu uma decisão ou foi processado.",
  verification_in_progress: "Verificação em andamento. Atualize os detalhes antes de decidir.",
  event_type_not_approvable: "Este tipo de evento não permite aprovação de assinatura.",
  internal_binding_mismatch: "O vínculo interno diverge da correlação encontrada.",
  sale_confirmed_subscription_unconfirmed: "Venda confirmada; vínculo e período recorrente não confirmados.",
  api_sale_not_paid: "A API não confirmou uma venda paga.",
};

export function canReviewBilling(role?: string | null) {
  return ["admin", "owner"].includes((role ?? "").trim().toLowerCase());
}

export function reviewCanApprove(review: BillingReview, busy: boolean) {
  return !busy && review.can_approve && review.verification_status === "manual_review" && !review.decision;
}

export function reviewReason(code: string) {
  return reviewReasons[code] ?? "Evidência insuficiente para aprovação. Revisão necessária.";
}
