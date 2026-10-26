import { createElement as h } from "react";
import type { BillingReview } from "../../lib/billingReviews.ts";

// Explicit fields only. No generic object/JSON rendering in an administrative view.
export function BillingReviewEvidence({ review }: { review: BillingReview }) {
  const fields: [string, string | number | null][] = [
    ["Evento", review.billing_event_id], ["Provider", review.provider], ["Tipo", review.event_type],
    ["Pedido externo", review.order_id], ["Assinatura externa (referência recebida)", review.external_subscription_id],
    ["Produto", review.product_id], ["Oferta externa (referência recebida)", review.external_offer_id],
    ["Plano candidato", review.candidate_plan_name], ["Tenant candidato", review.candidate_tenant_id],
    ["Status da verificação", review.verification_status], ["Venda confirmada", review.sale_status],
    ["Recebido em", review.received_at], ["Consultado na API em", review.sale_checked_at],
    ["Início do período confiável", review.period_start], ["Fim do período confiável", review.period_end],
    ["Decisão", review.decision], ["ID do administrador", review.decided_by], ["Decidido em", review.decided_at],
  ];
  return h("dl", { className: "grid gap-3 text-sm sm:grid-cols-2" }, ...fields.map(([label, value]) =>
    h("div", { key: label }, h("dt", { className: "font-medium text-slate-600" }, label),
      h("dd", { className: "break-all text-slate-900" }, value ?? "—"))));
}
