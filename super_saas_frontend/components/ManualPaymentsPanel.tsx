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
}
interface ManualPaymentPage {
  items: ManualPayment[]; total: number; pending_cents: number; paid_cents: number;
}
const PAGE_SIZE = 25;

export function ManualPaymentsPanel({ fromDate, toDate }: { fromDate: string; toDate: string }) {
  const { data: session } = useSession();
  const allowed = canManagePayments(session?.role);
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("pending");
  const [offset, setOffset] = useState(0);
  const [selection, setSelection] = useState<ManualPayment | null>(null);
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

  async function confirmPayment() {
    if (!selection || submitting.current) return;
    submitting.current = true; setBusy(true); setError(""); setNotice("");
    try {
      await api.post(`/api/orders/${selection.order_id}/payments/${selection.id}/status`, { status: "paid" });
      setSelection(null);
      setNotice("Recebimento registrado. O status de preparo e entrega do pedido não foi alterado.");
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
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-amber-50 p-4"><p className="text-sm">Pendente no período</p><strong>{data ? formatBRL(data.pending_cents) : "—"}</strong></div>
        <div className="rounded-xl bg-emerald-50 p-4"><p className="text-sm">Recebido dos pagamentos criados no período</p><strong>{data ? formatBRL(data.paid_cents) : "—"}</strong></div>
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
        <div className="overflow-x-auto"><Table><TableHeader><TableRow>
          <TableHead>Pedido / criação</TableHead><TableHead>Método</TableHead><TableHead>Valor</TableHead><TableHead>Pagamento</TableHead><TableHead>Recebimento</TableHead><TableHead>Ação</TableHead>
        </TableRow></TableHeader><TableBody>
          {data.items.map(payment => <TableRow key={payment.id}>
            <TableCell>#{payment.order_number}<span className="block text-xs text-slate-500">{new Date(payment.created_at).toLocaleString("pt-BR")}</span></TableCell>
            <TableCell>{paymentMethodLabel(payment.method)}</TableCell><TableCell>{formatBRL(payment.amount_cents)}</TableCell>
            <TableCell>{paymentStatusLabel(payment.status)}</TableCell>
            <TableCell>{payment.paid_at ? new Date(payment.paid_at).toLocaleString("pt-BR") : "Ainda não confirmado"}{payment.confirmed_by && <span className="block text-xs">Por {payment.confirmed_by}</span>}</TableCell>
            <TableCell>{payment.can_confirm ? <Button disabled={busy || isFetching} onClick={() => { setSelection(payment); setError(""); }}>Confirmar pagamento</Button> : payment.status === "pending" ? "Pedido cancelado: confira com a gestão" : "—"}</TableCell>
          </TableRow>)}
          {!data.items.length && <TableRow><TableCell colSpan={6}>Nenhum pagamento nesta situação e período.</TableCell></TableRow>}
        </TableBody></Table></div>
        <div className="flex items-center justify-between gap-2 text-sm"><span>{data.total} pagamento(s)</span><div className="flex gap-2"><Button variant="outline" disabled={!offset || isFetching} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</Button><Button variant="outline" disabled={offset + PAGE_SIZE >= data.total || isFetching} onClick={() => setOffset(offset + PAGE_SIZE)}>Próxima</Button></div></div>
      </>}
      <dialog ref={dialog} aria-labelledby="confirm-payment-title" aria-describedby="confirm-payment-description" className="w-[calc(100%-2rem)] max-w-md rounded-2xl p-6 shadow-xl backdrop:bg-black/40" onCancel={e => { e.preventDefault(); if (!busy) setSelection(null); }}>
        {selection && <div className="space-y-4">
          <h2 id="confirm-payment-title" className="text-lg font-semibold">Confirmar recebimento do pedido #{selection.order_number}?</h2>
          <p id="confirm-payment-description">Confirme que a loja já recebeu <strong>{formatBRL(selection.amount_cents)}</strong> por <strong>{paymentMethodLabel(selection.method)}</strong>. Esta ação registra o recebimento no financeiro; não realiza uma cobrança.</p>
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-2"><Button autoFocus variant="outline" disabled={busy} onClick={() => setSelection(null)}>Voltar</Button><Button disabled={busy} onClick={() => void confirmPayment()}>{busy ? "Registrando..." : "Sim, recebi o pagamento"}</Button></div>
        </div>}
      </dialog>
    </CardContent>
  </Card>;
}
