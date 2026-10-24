"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useSession } from "@/hooks/use-session";
import { canManagePayments, formatBRL, paymentMethodLabel, paymentStatusLabel } from "@/lib/manualPayments";
import { Button } from "@/components/ui/button";
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
  return <Card>
    <CardHeader><CardTitle>Recebimentos da loja</CardTitle><p className="text-sm text-slate-500">Pagamentos diretos, por data de criação do pagamento. Confirme somente após conferir o recebimento. Entregar o pedido não confirma o pagamento.</p></CardHeader>
    <CardContent className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl bg-amber-50 p-4"><p className="text-sm">Pendente no período</p><strong>{data ? formatBRL(data.pending_cents) : "—"}</strong></div>
        <div className="rounded-xl bg-emerald-50 p-4"><p className="text-sm">Recebido dos pagamentos criados no período</p><strong>{data ? formatBRL(data.paid_cents) : "—"}</strong></div>
        <div className="rounded-xl bg-slate-50 p-4"><p className="text-sm">Pagamentos cancelados no período</p><strong>{data ? formatBRL(data.canceled_cents ?? 0) : "—"}</strong></div>
        <div className="rounded-xl bg-rose-50 p-4"><p className="text-sm">Devoluções dos pagamentos criados no período</p><strong>{data ? formatBRL(data.refunded_cents ?? 0) : "—"}</strong></div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm">Situação <select aria-label="Situação do pagamento" className="ml-2 rounded-md border p-2" value={status} onChange={e => { setStatus(e.target.value); setOffset(0); }}>
          {["pending", "paid", "canceled", "refunded", "all"].map(value => <option key={value} value={value}>{value === "all" ? "Todos" : paymentStatusLabel(value)}</option>)}
        </select></label>
        <Button variant="outline" disabled={isFetching || busy} onClick={() => void refetch()}>Atualizar recebimentos</Button>
      </div>
      {notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}
      {isLoading && <p role="status">Carregando recebimentos...</p>}
      {isError && <p role="alert" className="text-sm text-red-600">Não foi possível carregar os recebimentos. Use “Atualizar recebimentos” para tentar novamente.</p>}
      {!isError && data && <>
        <div className="overflow-x-auto"><Table mobileCards><TableHeader><TableRow>
          <TableHead>Pedido / criação</TableHead><TableHead>Método</TableHead><TableHead>Valor</TableHead><TableHead>Pagamento</TableHead><TableHead>Recebimento / histórico</TableHead><TableHead>Ação</TableHead>
        </TableRow></TableHeader><TableBody>
          {data.items.map(payment => <TableRow key={payment.id}>
            <TableCell mobileLabel="Pedido / criação">#{payment.order_number}<span className="block text-xs text-slate-500">{new Date(payment.created_at).toLocaleString("pt-BR")}</span></TableCell>
            <TableCell mobileLabel="Método">{paymentMethodLabel(payment.method)}</TableCell><TableCell mobileLabel="Valor">{formatBRL(payment.amount_cents)}</TableCell>
            <TableCell mobileLabel="Pagamento">{paymentStatusLabel(payment.status)}</TableCell>
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
        </TableBody></Table></div>
        <div className="flex flex-col items-center justify-between gap-3 text-sm sm:flex-row"><span>{data.total} pagamento(s)</span><div className="flex gap-2"><Button variant="outline" disabled={!offset || isFetching} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</Button><Button variant="outline" disabled={offset + PAGE_SIZE >= data.total || isFetching} onClick={() => setOffset(offset + PAGE_SIZE)}>Próxima</Button></div></div>
      </>}
      <dialog ref={dialog} aria-labelledby="confirm-payment-title" aria-describedby="confirm-payment-description" className="w-[calc(100%-2rem)] max-w-md rounded-2xl p-6 shadow-xl backdrop:bg-black/40" onCancel={e => { e.preventDefault(); if (!busy) setSelection(null); }}>
        {selection && <form className="space-y-4" onSubmit={e => { e.preventDefault(); void confirmPayment(); }}>
          <h2 id="confirm-payment-title" className="text-lg font-semibold">{action === "paid" ? "Confirmar recebimento" : action === "canceled" ? "Cancelar pagamento pendente" : "Registrar devolução"} do pedido #{selection.order_number}?</h2>
          <div id="confirm-payment-description" className="space-y-2 text-sm">
            <p><strong>{formatBRL(selection.amount_cents)}</strong> · {paymentMethodLabel(selection.method)}</p>
            <p className="text-xs text-slate-500">Pagamento criado em {new Date(selection.created_at).toLocaleString("pt-BR")}</p>
            {action === "paid" && <p>Confirme que a loja já recebeu esse valor. Esta ação registra o recebimento no financeiro; não realiza uma cobrança.</p>}
            {action === "canceled" && <p>Este pagamento ainda não foi recebido. O cancelamento não movimenta o caixa e não cancela o pedido.</p>}
            {action === "refunded" && <><p>Registre somente após a loja devolver o valor integral ao cliente por fora do Fomizero. Será registrada uma saída no financeiro.</p><p>Esta ação não faz Pix ou estorno no cartão, não recupera taxas e não altera o pedido nem repõe estoque.</p></>}
          </div>
          {action !== "paid" && <div className="space-y-2">
            <label htmlFor="payment-reason" className="block text-sm font-medium">Motivo obrigatório</label>
            <textarea id="payment-reason" aria-label="Motivo" value={reason} onChange={e => setReason(e.target.value)} minLength={5} maxLength={500} required disabled={busy} rows={3} className="w-full rounded-md border p-2" />
            <p className="text-xs text-slate-500">De 5 a 500 caracteres. Este motivo ficará no histórico.</p>
          </div>}
          {action === "refunded" && <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={returned} onChange={e => setReturned(e.target.checked)} disabled={busy} required /><span>Confirmo que a loja já devolveu o valor integral ao cliente.</span></label>}
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
          <div className="flex flex-wrap justify-end gap-2"><Button autoFocus type="button" variant="outline" disabled={busy} onClick={() => setSelection(null)}>Voltar</Button><Button type="submit" disabled={busy || !canSubmit}>{busy ? "Registrando..." : action === "paid" ? "Sim, recebi o pagamento" : action === "canceled" ? "Sim, cancelar pagamento" : "Sim, registrar devolução"}</Button></div>
        </form>}
      </dialog>
    </CardContent>
  </Card>;
}
