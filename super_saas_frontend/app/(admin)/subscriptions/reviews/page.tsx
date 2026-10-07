"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AccessDenied } from "@/components/access-denied";
import { BillingReviewEvidence } from "@/components/admin/BillingReviewEvidence";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useSession } from "@/hooks/use-session";
import { api } from "@/lib/api";
import { BillingReview, canReviewBilling, reviewCanApprove, reviewNotice, reviewReason } from "@/lib/billingReviews";

const ROOT = "/api/admin/billing/reviews";

export default function BillingReviewsPage() {
  const { data: session, isLoading: sessionLoading } = useSession();
  const permitted = canReviewBilling(session?.role);
  const cache = useQueryClient();
  const [selected, setSelected] = useState<number | null>(null);
  const [eventType, setEventType] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [planId, setPlanId] = useState("");
  const [offset, setOffset] = useState(0);
  const [reason, setReason] = useState("insufficient_evidence");
  const [message, setMessage] = useState("");
  const list = useQuery({
    queryKey: ["billing-reviews", session?.tenant_id, eventType, fromDate, planId, offset], enabled: permitted,
    queryFn: () => {
      const query = new URLSearchParams({ limit: "50", offset: String(offset) });
      if (eventType) query.set("event_type", eventType);
      if (fromDate) query.set("from_date", new Date(`${fromDate}T00:00:00`).toISOString());
      if (planId) query.set("plan_id", planId);
      return api.get<BillingReview[]>(`${ROOT}?${query}`);
    },
  });
  const detail = useQuery({
    queryKey: ["billing-review", session?.tenant_id, selected], enabled: permitted && selected !== null,
    queryFn: () => api.get<BillingReview>(`${ROOT}/${selected}`), retry: false,
  });
  const decision = useMutation({
    mutationFn: ({ id, approve }: { id: number; approve: boolean }) =>
      api.post<BillingReview>(`${ROOT}/${id}/${approve ? "approve" : "reject"}`, approve ? undefined : { reason }, { "X-Billing-Review": "1" }),
    onSuccess: (result) => {
      cache.setQueryData(["billing-review", session?.tenant_id, result.billing_event_id], result);
      setMessage(result.decision === "binding_approved" ? "Vínculo validado. O acesso continua pendente por ausência de período confiável (manual_review_period_missing)." : result.decision === "approved" ? "Assinatura aprovada e decisão registrada." : "Evento rejeitado e preservado para auditoria.");
      void cache.invalidateQueries({ queryKey: ["billing-reviews"] });
    },
    onError: () => {
      setMessage("Não foi possível registrar a decisão. Atualize as evidências antes de tentar novamente.");
      void detail.refetch();
      void cache.invalidateQueries({ queryKey: ["billing-reviews"] });
    },
  });
  if (sessionLoading) return <p>Carregando sessão...</p>;
  if (!permitted) return <AccessDenied backHref="/dashboard" />;
  const current = detail.data;
  return <div className="space-y-6">
    <Card><CardHeader><CardTitle>Assinaturas &gt; Revisões pendentes</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-slate-600">Somente eventos vinculados ao seu tenant por correlação interna confiável.</p>
        <div className="flex flex-wrap gap-3">
          <label className="text-sm">Tipo de evento<select className="block rounded border p-2" value={eventType} onChange={e => { setEventType(e.target.value); setOffset(0); }}>
            <option value="">Todos</option><option value="order_approved">Compra aprovada</option><option value="subscription_renewed">Renovação</option>
          </select></label>
          <label className="text-sm">Recebidos a partir de<Input type="date" value={fromDate} onChange={e => { setFromDate(e.target.value); setOffset(0); }} /></label>
          <label className="text-sm">ID do plano interno<Input type="number" min="1" value={planId} onChange={e => { setPlanId(e.target.value); setOffset(0); }} /></label>
          <Button variant="outline" onClick={() => void list.refetch()}>Atualizar</Button>
        </div>
        {list.isLoading && <p>Carregando revisões...</p>}
        {list.isError && <p role="alert">Não foi possível carregar a fila. Tente atualizar.</p>}
        {list.data?.length === 0 && <p>Nenhuma revisão pendente nesta página.</p>}
        <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>
          {["Evento", "Status", "Plano candidato", "Tenant", "Recebido em", "Ação"].map(t => <th className="p-2" key={t}>{t}</th>)}
        </tr></thead><tbody>{list.data?.map(row => <tr key={row.billing_event_id} className="border-t">
          <td className="p-2">#{row.billing_event_id}<div>{row.event_type}</div></td><td className="p-2">{row.decision === "binding_approved" ? "Vínculo validado; vigência pendente" : "Revisão pendente"}</td>
          <td className="p-2">{row.candidate_plan_name ?? "Não identificado"}</td><td className="p-2">#{row.candidate_tenant_id}</td>
          <td className="p-2">{new Date(row.received_at).toLocaleString("pt-BR")}</td><td className="p-2"><Button variant="outline" onClick={() => { setSelected(row.billing_event_id); setMessage(""); decision.reset(); }}>Revisar</Button></td>
        </tr>)}</tbody></table></div>
        <div className="flex gap-3"><Button variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Anterior</Button>
          <Button variant="outline" disabled={!list.data || list.data.length < 50} onClick={() => setOffset(offset + 50)}>Próxima</Button></div>
      </CardContent></Card>
    {selected !== null && <section aria-label="Revisar assinatura" className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4 flex justify-between"><h2 className="text-lg font-semibold">Revisar evento #{selected}</h2>
        <Button variant="outline" disabled={decision.isPending} onClick={() => setSelected(null)}>Fechar</Button></div>
      {detail.isLoading && <p>Carregando evidência...</p>}{detail.isError && <p role="alert">Detalhes indisponíveis. Nenhuma decisão pode ser tomada.</p>}
      {current && !detail.isError && <div className="space-y-4">
        <p className="rounded border border-amber-200 bg-amber-50 p-3">{current.sale_status === "paid" ? reviewNotice : "Venda ainda não confirmada como paga pela API oficial. Aprovação indisponível."}</p>
        <BillingReviewEvidence review={current} /><p>{reviewReason(current.reason)}</p>
        <ul className="list-disc pl-5">{current.approval_blockers.map(code => <li key={code}>{reviewReason(code)}</li>)}</ul>
        {current.decision === "binding_approved" && current.access_pending_period && <p role="status" className="rounded bg-amber-50 p-3">Vínculo validado. O acesso continua pendente por ausência de período confiável (manual_review_period_missing).</p>}
        <p className="text-sm text-slate-600">{current.access_pending_period ? "A aprovação confirma apenas o vínculo comercial. A assinatura permanece inativa e o acesso aguarda período confiável." : "A aprovação confirma o vínculo e libera acesso pelo período confiável exibido."} Nenhum período é deduzido do webhook.</p>
        <Button disabled={!reviewCanApprove(current, decision.isPending || detail.isFetching)} onClick={() => decision.mutate({ id: current.billing_event_id, approve: true })}>{current.access_pending_period ? "Aprovar vínculo da assinatura" : "Aprovar assinatura"}</Button>
        <div className="flex flex-wrap items-end gap-3"><label className="text-sm">Motivo da rejeição<select className="block rounded border p-2" value={reason} onChange={e => setReason(e.target.value)}>
          <option value="insufficient_evidence">Evidência insuficiente</option><option value="incorrect_binding">Vínculo incorreto</option>
          <option value="incorrect_plan">Plano incorreto</option><option value="duplicate_sale">Venda duplicada</option><option value="invalid_sale">Venda inválida</option>
        </select></label><Button variant="outline" disabled={decision.isPending || detail.isFetching || current.verification_status !== "manual_review" || !!current.decision}
          onClick={() => decision.mutate({ id: current.billing_event_id, approve: false })}>Rejeitar</Button></div>
      </div>}
      {message && <p role="status" className="mt-4">{message}</p>}
    </section>}
  </div>;
}
