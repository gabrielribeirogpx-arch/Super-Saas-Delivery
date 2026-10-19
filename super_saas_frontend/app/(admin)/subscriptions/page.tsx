"use client";
import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSession } from "@/hooks/use-session";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { AccessDenied } from "@/components/access-denied";
import { MySubscription, subscriptionStatuses, subscriptionFeatureNames, validatedHotmartCheckout } from "@/lib/subscriptions";

const ROOT = "/api/admin/billing/subscription";
const money = (cents: number) => (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const date = (value: string) => new Date(value).toLocaleString("pt-BR");

export default function SubscriptionPage() {
  const session = useSession();
  const allowed = ["owner", "admin"].includes(session.data?.role ?? "");
  const data = useQuery({ queryKey: ["my-subscription", session.data?.tenant_id], enabled: allowed,
    queryFn: () => api.get<MySubscription>(ROOT), retry: false, refetchInterval: 15000 });
  const dialog = useRef<HTMLDialogElement>(null);
  const submitting = useRef(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function action(plan?: string) {
    if (submitting.current) return;
    submitting.current = true; setBusy(true); setMessage("");
    try {
      if (plan) {
        const result = await api.post<{ checkout_url: string }>(ROOT + "/checkout", { plan_code: plan }, { "X-Billing-Action": "1" });
        window.location.assign(validatedHotmartCheckout(result.checkout_url));
      } else {
        await api.post(ROOT + "/cancel", undefined, { "X-Billing-Action": "1" });
        dialog.current?.close();
        setMessage("Solicitação registrada. Aguarde a confirmação do cancelamento pela Hotmart.");
      }
      await data.refetch();
    } catch {
      setMessage(plan ? "Não foi possível abrir a contratação. Atualize a assinatura ou fale com o suporte." : "Não foi possível solicitar o cancelamento. Tente novamente ou gerencie sua compra na Hotmart.");
    } finally { submitting.current = false; setBusy(false); }
  }
  if (session.isLoading) return <p>Carregando sessão...</p>;
  if (!allowed) return <AccessDenied backHref="/dashboard" />;
  const current = data.data;
  return <div className="mx-auto max-w-5xl space-y-6">
    <div><h1 className="text-2xl font-semibold">Minha assinatura</h1><p className="mt-1 text-sm text-slate-600">Plano do seu restaurante no Fomizero.</p></div>
    {message && <p role="status" className="rounded-lg border bg-white p-4 text-sm">{message}</p>}
    {data.isLoading && <p>Carregando assinatura...</p>}
    {data.isError && <div role="alert" className="rounded-lg border bg-white p-5"><p>Não foi possível consultar sua assinatura.</p><Button variant="outline" onClick={() => void data.refetch()}>Tentar novamente</Button></div>}
    {current && <>
      <section className="space-y-4 rounded-xl border bg-white p-6" aria-label="Assinatura atual">
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">{current.plan_name ?? "Seu plano"}</h2><span className="rounded-full bg-slate-100 px-3 py-1 text-sm">{subscriptionStatuses[current.status] ?? "Em análise"}</span></div>
        {current.period_end && <p className="text-sm">Período contratado até <strong>{date(current.period_end)}</strong>.</p>}
        {current.cancel_pending && <p role="status" className="text-sm text-amber-800">Cancelamento solicitado. A confirmação da Hotmart está pendente; novas cobranças só deixam de ser previstas após essa confirmação.</p>}
        {current.cancel_at_period_end && <p className="text-sm text-emerald-800">Renovação cancelada. O acesso continua até o fim do período pago.</p>}
        {current.checkout_pending && current.status !== "active" && <p className="text-sm text-amber-800">Contratação iniciada. Se já pagou, aguarde a confirmação. Esta tela atualiza automaticamente.</p>}
        {!current.enabled && <p className="text-sm text-slate-600">A contratação online ainda não está disponível. Fale com o suporte do Fomizero.</p>}
        {current.provider && current.provider !== "hotmart" && <p className="text-sm text-slate-600">Sua assinatura usa outro meio de contratação. Fale com o suporte para migrar sem cobranças duplicadas.</p>}
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" disabled={busy || data.isFetching} onClick={() => void data.refetch()}>Atualizar assinatura</Button>
          {current.provider === "hotmart" && <a href="https://consumer.hotmart.com/" target="_blank" rel="noopener noreferrer" className="rounded border px-4 py-2 text-sm">Gerenciar pagamentos na Hotmart</a>}
          {current.can_cancel && !current.cancel_pending && <Button variant="outline" disabled={busy} onClick={() => dialog.current?.showModal()}>Cancelar renovação</Button>}
        </div>
      </section>
      {current.enabled && current.can_checkout && <section aria-label="Planos disponíveis" className="grid gap-4 md:grid-cols-3">
        {current.offers.map(offer => <article key={offer.code} className="flex flex-col rounded-xl border bg-white p-6">
          <h2 className="text-lg font-semibold">{offer.name}</h2><p className="my-3"><strong className="text-2xl">{money(offer.price_cents)}</strong><span className="text-sm text-slate-600"> / mês</span></p>
          <ul className="mb-5 flex-1 space-y-2 text-sm">{offer.features.filter(f => f.enabled).map(f => <li key={f.code}>{subscriptionFeatureNames[f.code] ?? "Recurso do plano"}{f.limit !== null ? `: ${f.limit}` : ""}</li>)}</ul>
          <Button disabled={busy} onClick={() => void action(offer.code)}>{busy ? "Abrindo..." : current.checkout_pending ? `Continuar com ${offer.name}` : `Assinar ${offer.name}`}</Button>
        </article>)}
        {!current.offers.length && <p className="text-sm">Nenhum plano está disponível para contratação agora. Fale com o suporte.</p>}
      </section>}
      {current.enabled && current.can_checkout && <p className="text-sm text-slate-600">Você concluirá a assinatura mensal no checkout da Hotmart. Confira valor, recorrência e condições antes de pagar. O acesso será liberado após a confirmação do pagamento.</p>}
      {current.events.length > 0 && <section className="rounded-xl border bg-white p-6"><h2 className="mb-3 font-semibold">Atualizações da assinatura</h2><ul className="space-y-2 text-sm">{current.events.map((event, i) => <li key={`${event.received_at}-${i}`}>{date(event.received_at)} — {event.status === "processed" ? "Atualização processada" : "Atualização em análise"}</li>)}</ul></section>}
    </>}
    <dialog ref={dialog} className="w-[calc(100%-2rem)] max-w-md rounded-xl p-6 shadow-xl backdrop:bg-black/40" onCancel={e => { if (busy) e.preventDefault(); }}>
      <h2 className="font-semibold">Cancelar a renovação?</h2><p className="my-4 text-sm">Vamos solicitar o cancelamento das próximas cobranças à Hotmart. O período já pago será preservado. Esta ação não solicita reembolso.</p>
      <div className="flex justify-end gap-3"><Button variant="outline" disabled={busy} onClick={() => dialog.current?.close()}>Voltar</Button><Button disabled={busy} onClick={() => void action()}>{busy ? "Solicitando..." : "Confirmar cancelamento"}</Button></div>
    </dialog>
  </div>;
}
