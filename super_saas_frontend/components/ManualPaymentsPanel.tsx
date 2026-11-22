"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock3, CreditCard, RefreshCw, RotateCcw, ShieldCheck, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useSession } from "@/hooks/use-session";
import { canManagePayments, formatBRL, paymentMethodLabel, paymentStatusLabel } from "@/lib/manualPayments";
import { Button } from "@/components/ui/button";
import { LoadingExperience } from "@/components/ui/loading-experience";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface ManualPayment {
  id: number; order_id: number; order_number: number; method: string;
  amount_cents: number; status: string; order_status: string;
  created_at: string; paid_at: string | null; confirmed_by: string | null; can_confirm: boolean;
  can_cancel?: boolean; can_refund?: boolean;
  last_adjustment?: { status: string; reason: string | null; recorded_at: string; recorded_by: string } | null;
}
interface ManualPaymentPage {
  items: ManualPayment[]; total: number; pending_cents: number; paid_cents: number; canceled_cents?: number; refunded_cents?: number;
}
type PaymentAction = "paid" | "canceled" | "refunded";
const PAGE_SIZE = 25;
const ACTION_NOTICE: Record<PaymentAction, string> = {
  paid: "Recebimento registrado. O status de preparo e entrega do pedido não foi alterado.",
  canceled: "Pagamento pendente cancelado. Nenhuma entrada ou saída foi lançada no caixa. O pedido não foi cancelado.",
  refunded: "Devolução registrada no financeiro. Nenhuma transferência bancária foi realizada. O pedido e o estoque não foram alterados.",
};

export function ManualPaymentsPanel({ fromDate, toDate }: { fromDate: string; toDate: string }) {
  const { data: session } = useSession();
  const allowed = canManagePayments(session?.role);
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("pending");
  const [offset, setOffset] = useState(0);
  const [selection, setSelection] = useState<ManualPayment | null>(null);
  const [action, setAction] = useState<PaymentAction>("paid");
  const [reason, setReason] = useState("");
  const [returned, setReturned] = useState(false);
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (selection && !dialog.current?.open) dialog.current?.showModal();
    if (!selection) dialog.current?.close();
  }, [selection]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  // Reset pagination when the date range changes without retaining another range's rows.
  const range = `${fromDate}:${toDate}`;
  const [previousRange, setPreviousRange] = useState(range);
  if (range !== previousRange) { setPreviousRange(range); setOffset(0); }
  const { data, isLoading, isError, isFetching, refetch } = useQuery({
    queryKey: ["manual-payments", session?.tenant_id, fromDate, toDate, status, offset],
    enabled: allowed,
    queryFn: () => api.get<ManualPaymentPage>(`/api/finance/manual-payments?${new URLSearchParams({ from: fromDate, to: toDate, status, limit: String(PAGE_SIZE), offset: String(offset) })}`),
  });

  function openAction(payment: ManualPayment, nextAction: PaymentAction) {
    setSelection(payment); setAction(nextAction); setReason(""); setReturned(false); setError("");
  }
  const reasonValid = reason.trim().length >= 5 && reason.trim().length <= 500;
  const canSubmit = action === "paid" || (reasonValid && (action !== "refunded" || returned));
  async function confirmPayment() {
    if (!selection || submitting.current) return;
    if (!canSubmit) {
      setError(action === "refunded" && !returned ? "Confirme que a loja já devolveu o valor ao cliente." : "Informe um motivo entre 5 e 500 caracteres.");
      return;
    }
    submitting.current = true; setBusy(true); setError(""); setNotice("");
    try {
      await api.post(`/api/orders/${selection.order_id}/payments/${selection.id}/status`, { status: action, ...(action !== "paid" ? { reason: reason.trim() } : {}) });
      setSelection(null);
      setNotice(ACTION_NOTICE[action]);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["manual-payments"] }),
        queryClient.invalidateQueries({ queryKey: ["finance"] }),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível confirmar. Atualize a lista antes de tentar novamente.");
      void queryClient.invalidateQueries({ queryKey: ["manual-payments"] });
    } finally { submitting.current = false; setBusy(false); }
  }

  if (!session) return null;
  if (!allowed) return <p className="text-sm text-slate-600">Recebimentos disponíveis apenas para proprietário, administrador ou caixa.</p>;
  return <Card className="overflow-hidden rounded-[28px] border-slate-200/70 shadow-[0_20px_55px_-42px_rgba(15,23,42,0.5)]">
    <CardHeader className="border-b border-slate-100 px-5 py-5 sm:px-7"><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">Conciliação</p><CardTitle className="mt-1 text-xl">Recebimentos da loja</CardTitle></div><span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-brand-50 text-brand-600"><CreditCard className="h-5 w-5" aria-hidden="true" /></span></div><p className="max-w-3xl text-sm leading-relaxed text-slate-500">Pagamentos diretos, por data de criação do pagamento. Confirme somente após conferir o recebimento. Entregar o pedido não confirma o pagamento.</p></CardHeader>
    <CardContent className="space-y-5 p-4 sm:p-6">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-amber-100 bg-amber-50/60 p-4"><div className="flex items-center justify-between"><p className="text-xs font-bold uppercase tracking-[0.12em] text-amber-700/70">Pendente</p><Clock3 className="h-4 w-4 text-amber-600" aria-hidden="true" /></div><strong className="mt-3 block text-xl tracking-tight text-slate-950">{data ? formatBRL(data.pending_cents) : "—"}</strong><p className="mt-1 text-[11px] text-amber-800/60">Aguardando conferência</p></div>
        <div className="rounded-2xl border border-emerald-100 bg-emerald-50/60 p-4"><div className="flex items-center justify-between"><p className="text-xs font-bold uppercase tracking-[0.12em] text-emerald-700/70">Recebido</p><CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" /></div><strong className="mt-3 block text-xl tracking-tight text-slate-950">{data ? formatBRL(data.paid_cents) : "—"}</strong><p className="mt-1 text-[11px] text-emerald-800/60">Confirmado no período</p></div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4"><div className="flex items-center justify-between"><p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Cancelado</p><XCircle className="h-4 w-4 text-slate-500" aria-hidden="true" /></div><strong className="mt-3 block text-xl tracking-tight text-slate-950">{data ? formatBRL(data.canceled_cents ?? 0) : "—"}</strong><p className="mt-1 text-[11px] text-slate-500">Sem entrada no caixa</p></div>
        <div className="rounded-2xl border border-rose-100 bg-rose-50/60 p-4"><div className="flex items-center justify-between"><p className="text-xs font-bold uppercase tracking-[0.12em] text-rose-700/70">Devolvido</p><RotateCcw className="h-4 w-4 text-rose-600" aria-hidden="true" /></div><strong className="mt-3 block text-xl tracking-tight text-slate-950">{data ? formatBRL(data.refunded_cents ?? 0) : "—"}</strong><p className="mt-1 text-[11px] text-rose-800/60">Registrado como saída</p></div>
      </div>
      <div className="flex flex-col gap-3 rounded-2xl border border-slate-200/80 bg-slate-50/60 p-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="flex items-center justify-between gap-3 text-xs font-bold uppercase tracking-[0.12em] text-slate-500 sm:justify-start">Situação <select aria-label="Situação do pagamento" className="min-h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold normal-case tracking-normal text-slate-800 shadow-sm outline-none focus:ring-2 focus:ring-brand-300" value={status} onChange={e => { setStatus(e.target.value); setOffset(0); }}>
          {["pending", "paid", "canceled", "refunded", "all"].map(value => <option key={value} value={value}>{value === "all" ? "Todos" : paymentStatusLabel(value)}</option>)}
        </select></label>
        <Button variant="outline" className="rounded-xl bg-white" disabled={isFetching || busy} onClick={() => void refetch()}><RefreshCw className={`mr-2 h-4 w-4 ${isFetching ? "animate-spin" : ""}`} aria-hidden="true" />Atualizar recebimentos</Button>
      </div>
      {notice && <p role="status" className="flex items-start gap-2 rounded-2xl border border-emerald-100 bg-emerald-50 p-3 text-sm font-medium text-emerald-800"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />{notice}</p>}
      {isLoading && <LoadingExperience label="Buscando recebimentos" compact />}
      {isError && <p role="alert" className="text-sm text-red-600">Não foi possível carregar os recebimentos. Use “Atualizar recebimentos” para tentar novamente.</p>}
      {!isError && data && <>
        <Table mobileCards containerClassName="rounded-2xl border border-slate-200/80"><TableHeader className="bg-slate-50/80"><TableRow>
          <TableHead>Pedido / criação</TableHead><TableHead>Método</TableHead><TableHead>Valor</TableHead><TableHead>Pagamento</TableHead><TableHead>Recebimento / histórico</TableHead><TableHead>Ação</TableHead>
        </TableRow></TableHeader><TableBody>
          {data.items.map(payment => <TableRow key={payment.id} className="hover:bg-slate-50/70">
            <TableCell mobileLabel="Pedido / criação"><strong className="text-slate-950">#{payment.order_number}</strong><span className="mt-1 block text-xs text-slate-500">{new Date(payment.created_at).toLocaleString("pt-BR")}</span></TableCell>
            <TableCell mobileLabel="Método"><span className="inline-flex rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">{paymentMethodLabel(payment.method)}</span></TableCell><TableCell mobileLabel="Valor" className="font-bold text-slate-950">{formatBRL(payment.amount_cents)}</TableCell>
            <TableCell mobileLabel="Pagamento"><span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ${payment.status === "paid" ? "bg-emerald-50 text-emerald-700" : payment.status === "pending" ? "bg-amber-50 text-amber-700" : payment.status === "refunded" ? "bg-rose-50 text-rose-700" : "bg-slate-100 text-slate-600"}`}><span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />{paymentStatusLabel(payment.status)}</span></TableCell>
            <TableCell mobileLabel="Recebimento / histórico">
              {payment.paid_at ? new Date(payment.paid_at).toLocaleString("pt-BR") : payment.status === "canceled" ? "Sem recebimento" : "Ainda não confirmado"}
              {payment.confirmed_by && <span className="block text-xs">Por {payment.confirmed_by}</span>}
              {payment.last_adjustment && <details className="mt-2 max-w-sm text-sm">
                <summary className="cursor-pointer font-medium">{payment.last_adjustment.status === "refunded" ? "Ver devolução" : "Ver cancelamento"}</summary>
                <p className="mt-2 whitespace-pre-wrap break-words">{payment.last_adjustment.reason || "Motivo não registrado no histórico antigo."}</p>
                <p className="mt-1 text-xs">Por {payment.last_adjustment.recorded_by} · {new Date(payment.last_adjustment.recorded_at).toLocaleString("pt-BR")}</p>
              </details>}
            </TableCell>
            <TableCell mobileLabel="Ação" mobileActions><div className="flex flex-wrap gap-2">
              {payment.can_confirm && <Button disabled={busy || isFetching} onClick={() => openAction(payment, "paid")}>Confirmar pagamento</Button>}
              {payment.can_cancel && <Button variant="outline" disabled={busy || isFetching} onClick={() => openAction(payment, "canceled")}>Cancelar pagamento</Button>}
              {payment.can_refund && <Button variant="outline" disabled={busy || isFetching} onClick={() => openAction(payment, "refunded")}>Registrar devolução</Button>}
              {!payment.can_confirm && payment.status === "pending" && <span>Recebimento bloqueado: pedido cancelado</span>}
              {!payment.can_confirm && !payment.can_cancel && !payment.can_refund && payment.status !== "pending" && "—"}
            </div></TableCell>
          </TableRow>)}
          {!data.items.length && <TableRow><TableCell colSpan={6}>Nenhum pagamento nesta situação e período.</TableCell></TableRow>}
        </TableBody></Table>
        <div className="flex flex-col items-center justify-between gap-3 rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-500 sm:flex-row"><span><strong className="text-slate-800">{data.total}</strong> pagamento(s)</span><div className="flex w-full gap-2 sm:w-auto"><Button className="flex-1 rounded-xl sm:flex-none" variant="outline" disabled={!offset || isFetching} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</Button><Button className="flex-1 rounded-xl sm:flex-none" variant="outline" disabled={offset + PAGE_SIZE >= data.total || isFetching} onClick={() => setOffset(offset + PAGE_SIZE)}>Próxima</Button></div></div>
      </>}
      <dialog ref={dialog} aria-labelledby="confirm-payment-title" aria-describedby="confirm-payment-description" className="w-[calc(100%-2rem)] max-w-md rounded-[24px] border border-white/70 p-0 shadow-2xl backdrop:bg-slate-950/55 backdrop:backdrop-blur-sm" onCancel={e => { e.preventDefault(); if (!busy) setSelection(null); }}>
        {selection && <form className="space-y-4" onSubmit={e => { e.preventDefault(); void confirmPayment(); }}>
          <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4"><span className="grid h-10 w-10 place-items-center rounded-xl bg-slate-950 text-white"><ShieldCheck className="h-5 w-5" aria-hidden="true" /></span><h2 id="confirm-payment-title" className="text-lg font-bold leading-tight">{action === "paid" ? "Confirmar recebimento" : action === "canceled" ? "Cancelar pagamento pendente" : "Registrar devolução"} do pedido #{selection.order_number}?</h2></div>
          <div className="space-y-4 px-5 pb-5"><div id="confirm-payment-description" className="space-y-2 rounded-2xl bg-slate-50 p-4 text-sm">
            <p><strong>{formatBRL(selection.amount_cents)}</strong> · {paymentMethodLabel(selection.method)}</p>
            <p className="text-xs text-slate-500">Pagamento criado em {new Date(selection.created_at).toLocaleString("pt-BR")}</p>
            {action === "paid" && <p>Confirme que a loja já recebeu esse valor. Esta ação registra o recebimento no financeiro; não realiza uma cobrança.</p>}
            {action === "canceled" && <p>Este pagamento ainda não foi recebido. O cancelamento não movimenta o caixa e não cancela o pedido.</p>}
            {action === "refunded" && <><p>Registre somente após a loja devolver o valor integral ao cliente por fora do Fomizero. Será registrada uma saída no financeiro.</p><p>Esta ação não faz Pix ou estorno no cartão, não recupera taxas e não altera o pedido nem repõe estoque.</p></>}
          </div>
          {action !== "paid" && <div className="space-y-2">
            <label htmlFor="payment-reason" className="block text-sm font-medium">Motivo obrigatório</label>
            <textarea id="payment-reason" aria-label="Motivo" value={reason} onChange={e => setReason(e.target.value)} minLength={5} maxLength={500} required disabled={busy} rows={3} className="w-full rounded-xl border border-slate-200 p-3 outline-none focus:ring-2 focus:ring-brand-300" />
            <p className="text-xs text-slate-500">De 5 a 500 caracteres. Este motivo ficará no histórico.</p>
          </div>}
          {action === "refunded" && <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={returned} onChange={e => setReturned(e.target.checked)} disabled={busy} required /><span>Confirmo que a loja já devolveu o valor integral ao cliente.</span></label>}
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><Button className="rounded-xl" autoFocus type="button" variant="outline" disabled={busy} onClick={() => setSelection(null)}>Voltar</Button><Button className="rounded-xl" type="submit" disabled={busy || !canSubmit}>{busy ? "Registrando..." : action === "paid" ? "Sim, recebi o pagamento" : action === "canceled" ? "Sim, cancelar pagamento" : "Sim, registrar devolução"}</Button></div></div>
        </form>}
      </dialog>
    </CardContent>
  </Card>;
}
