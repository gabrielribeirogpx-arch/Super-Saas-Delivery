"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

const endpoint = "/api/orders/wazza/requests";
const states = {
  pending_review: "Pendente de análise",
  rejected: "Rejeitada",
  manual_resolution: "Aguardando resolução manual",
  applied: "Aplicada",
  failed: "Falha na aplicação",
};
const reasons: Record<string, string> = {
  in_preparation: "Pedido em preparo",
  benefits_or_stock: "Há efeitos em benefícios ou estoque",
  payment_review: "Pagamento precisa de análise",
  other_channel: "Pedido de outro canal",
  operational_review: "Pedido precisa de análise operacional",
  customer_confirmed: "Alteração confirmada pelo cliente",
};
const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
type Action = "approve" | "reject" | "verify";
type Line = { name: string; quantity: number; modifiers?: { option_name?: string }[] };
function displayLine(line: Line) {
  const modifiers = line.modifiers?.flatMap(modifier => modifier.option_name ? [modifier.option_name] : []).join(", ");
  return `${line.quantity}× ${line.name}${modifiers ? ` (${modifiers})` : ""}`;
}
type Entry = {
  request_id: number;
  order_id: number;
  action: "edit" | "cancel";
  state: keyof typeof states;
  reason: string;
  before_cents: number;
  after_cents: number;
  before_items: Line[];
  after_items: Line[];
  created_at: string;
  decision_reason: string | null;
  resolution_reason: string | null;
  decided_by: number | null;
  decided_at: string | null;
  resolved_by: number | null;
  resolved_at: string | null;
};
type Page = { items: Entry[]; next: number | null };

export function WazzaOrderReviews({ tenantId, onDecision }: { tenantId: number; onDecision: () => void }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [cursors, setCursors] = useState<(number | null)[]>([null]);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const cursor = cursors[cursors.length - 1];
  const queue = useQuery({
    queryKey: ["wazza-order-reviews", tenantId, cursor],
    queryFn: () => api.get<Page>(cursor ? `${endpoint}?before=${cursor}` : endpoint),
    enabled: open,
  });
  const decision = useMutation({
    mutationFn: ({ id, action }: { id: number; action: Action }) =>
      api.post(`${endpoint}/${id}/decision`, { action, reason: notes[id]?.trim() }),
    onSuccess: (_, variables) => {
      setNotes(current => ({ ...current, [variables.id]: "" }));
      void queryClient.invalidateQueries({ queryKey: ["wazza-order-reviews", tenantId] });
      onDecision();
    },
  });
  function submit(id: number, action: Action) {
    decision.mutate({ id, action });
  }

  return (
    <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-4 sm:p-5" aria-label="Solicitações do WhatsApp">
      <Button variant="outline" onClick={() => setOpen(!open)} aria-expanded={open}>
        {open ? "Ocultar solicitações do WhatsApp" : "Ver solicitações do WhatsApp"}
      </Button>
      {open && <div className="mt-4 space-y-4">
        <h2 className="text-lg font-semibold">Solicitações do WhatsApp</h2>
        {queue.isLoading && <p role="status">Carregando solicitações…</p>}
        {queue.isError && <p role="alert">Não foi possível carregar as solicitações. Verifique sua permissão e tente novamente.</p>}
        {decision.isError && <p role="alert">Não foi possível concluir a decisão. Atualize a fila antes de tentar novamente.</p>}
        {queue.data?.items.length === 0 && <p>Nenhuma solicitação nesta página.</p>}
        {queue.data?.items.map(entry => <article key={entry.request_id} className="space-y-3 rounded-xl border border-slate-200 p-4">
          <div className="flex flex-wrap justify-between gap-2">
            <h3 className="font-semibold">{entry.action === "edit" ? "Edição" : "Cancelamento"} do pedido #{entry.order_id}</h3>
            <span className="rounded-md bg-slate-100 px-2 py-1 text-sm">{states[entry.state]}</span>
          </div>
          <p className="text-sm text-slate-600">{reasons[entry.reason] ?? "Análise do restaurante"} · {new Date(entry.created_at).toLocaleString("pt-BR")}</p>
          {entry.state === "manual_resolution" && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">
            A solicitação foi aprovada, mas ainda não foi aplicada ao pedido.
          </p>}
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div className="min-w-0 break-words"><dt className="font-medium">Pedido atual no momento da solicitação</dt><dd>{currency.format(entry.before_cents / 100)}</dd><dd>{entry.before_items.map(displayLine).join(", ") || "Sem itens detalhados"}</dd></div>
            <div className="min-w-0 break-words"><dt className="font-medium">Alteração proposta</dt><dd>{currency.format(entry.after_cents / 100)}</dd><dd>{entry.action === "cancel" ? "Cancelamento integral" : entry.after_items.map(displayLine).join(", ")}</dd></div>
          </dl>
          {entry.decision_reason && <p className="break-words text-sm">
            Decisão do operador #{entry.decided_by} em {new Date(entry.decided_at ?? entry.created_at).toLocaleString("pt-BR")}. {entry.decision_reason}
          </p>}
          {entry.resolution_reason && <p className="break-words text-sm">
            Verificação do operador #{entry.resolved_by} em {new Date(entry.resolved_at ?? entry.created_at).toLocaleString("pt-BR")}. {entry.resolution_reason}
          </p>}
          {(entry.state === "pending_review" || entry.state === "manual_resolution") && <div className="space-y-2">
            <label className="block text-sm font-medium" htmlFor={`wazza-note-${entry.request_id}`}>Motivo {entry.state === "manual_resolution" ? "da verificação" : "da decisão"}</label>
            <textarea id={`wazza-note-${entry.request_id}`} maxLength={300} rows={2} value={notes[entry.request_id] ?? ""}
              onChange={event => setNotes({ ...notes, [entry.request_id]: event.target.value })}
              className="w-full rounded-lg border border-slate-300 p-2 text-sm" />
            <div className="flex flex-wrap gap-2">
              {entry.state === "pending_review" ? <>
                <Button disabled={decision.isPending || (notes[entry.request_id]?.trim().length ?? 0) < 5} onClick={() => submit(entry.request_id, "approve")}>Autorizar alteração</Button>
                <Button variant="outline" disabled={decision.isPending || (notes[entry.request_id]?.trim().length ?? 0) < 5} onClick={() => submit(entry.request_id, "reject")}>Rejeitar</Button>
              </> : <Button disabled={decision.isPending || (notes[entry.request_id]?.trim().length ?? 0) < 5} onClick={() => submit(entry.request_id, "verify")}>Verificar nos registros oficiais</Button>}
            </div>
          </div>}
        </article>)}
        <div className="flex flex-wrap gap-2">
          {cursors.length > 1 && <Button variant="outline" onClick={() => setCursors(cursors.slice(0, -1))}>Página anterior</Button>}
          {queue.data?.next && <Button variant="outline" onClick={() => setCursors([...cursors, queue.data.next])}>Próxima página</Button>}
        </div>
      </div>}
    </section>
  );
}
