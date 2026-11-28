"use client";

import { useId, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { RequestErrorState } from "@/components/request-error-state";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

const endpoint = "/api/admin/ifood-orders";
const price = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const dateTime = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });
const states: Record<string, string> = {
  PLACED: "Aguardando confirmação",
  CONFIRMED: "Confirmado",
  PREPARATION_STARTED: "Em preparo",
  READY_TO_PICKUP: "Pronto para retirada",
  DISPATCHED: "Saiu para entrega",
  DELIVERED: "Entregue",
  CONCLUDED: "Concluído",
  CANCELLED: "Cancelado",
};
const orderTypes: Record<string, string> = { DELIVERY: "Entrega", TAKEOUT: "Retirada", DINE_IN: "Consumo no local" };
const paymentMethods: Record<string, string> = {
  CASH: "Dinheiro", CREDIT: "Crédito", DEBIT: "Débito", PIX: "Pix",
  MEAL_VOUCHER: "Vale-refeição", FOOD_VOUCHER: "Vale-alimentação",
  GIFT_CARD: "Vale-presente", DIGITAL_WALLET: "Carteira digital", OTHER: "Outro",
};

export interface IFoodItem {
  name: string;
  quantity: number;
  observations?: string | null;
  options: IFoodItem[];
}

export interface IFoodOrder {
  order_id: string;
  display_id: string;
  order_type: string;
  timing?: string;
  delivered_by?: string | null;
  scheduled_for?: string;
  total: number;
  items: IFoodItem[];
  created_at?: string;
  payment: { method: string; type: string }[];
  observations?: string;
  state: string;
  confirmation_pending: boolean;
  confirmation_deadline: string;
  can_confirm: boolean;
  ready_pending?: boolean;
  can_mark_ready?: boolean;
  dispatch_pending?: boolean;
  can_dispatch?: boolean;
  cancellation_status?: "pending" | "rejected" | null;
  can_cancel?: boolean;
}

export function IFoodItems({ items }: { items: IFoodItem[] }) {
  return (
    <ul className="space-y-1 pl-4">
      {items.map((item, index) => (
        <li key={index} className="list-disc break-words">
          {item.quantity}× {item.name}
          {item.observations && <p className="text-slate-600">{item.observations}</p>}
          {item.options.length > 0 && <IFoodItems items={item.options} />}
        </li>
      ))}
    </ul>
  );
}

function useIFoodConfirmation({ order, refresh }: {
  order: IFoodOrder;
  refresh: () => void;
}) {
  const confirm = useMutation({
    mutationFn: () => api.post<{ confirmation_pending: boolean }>(`${endpoint}/${order.order_id}/confirm`),
    onSuccess: refresh,
  });
  const sent = order.state === "PLACED" && (order.confirmation_pending || confirm.isSuccess);
  const expired = Date.parse(order.confirmation_deadline) <= Date.now();
  const state = sent ? "Confirmação enviada ao iFood"
    : order.state === "PLACED" && expired ? "Prazo de confirmação encerrado"
    : states[order.state] ?? order.state;

  return { confirm, state, canConfirm: order.can_confirm && !expired && !sent };
}

function IFoodConfirmButton({ confirm, canConfirm }: ReturnType<typeof useIFoodConfirmation>) {
  return (
    <>
      {confirm.error && (confirm.error instanceof ApiError && confirm.error.status !== 401 && confirm.error.status !== 403
        ? <p role="alert" className="text-red-700">{confirm.error.message}</p>
        : <RequestErrorState error={confirm.error} />)}
      {canConfirm && (
        <Button type="button" size="sm" disabled={confirm.isPending} onClick={() => confirm.mutate()}>
          {confirm.isPending ? "Enviando…" : "Confirmar pedido iFood"}
        </Button>
      )}
    </>
  );
}

function IFoodDispatchAction({ order, refresh }: { order: IFoodOrder; refresh: () => void }) {
  const dispatch = useMutation({
    mutationFn: () => api.post<{ dispatch_pending: boolean }>(`${endpoint}/${order.order_id}/dispatch`),
    onSuccess: refresh,
  });
  if (order.state !== "READY_TO_PICKUP") return null;
  if (order.dispatch_pending || dispatch.data?.dispatch_pending) {
    return <p role="status" className="text-sm text-slate-700">Despacho enviado. Aguardando retorno do iFood.</p>;
  }
  if (!order.can_dispatch) return null;

  return (
    <div className="space-y-2">
      {dispatch.error && (
        <p role="alert" className="text-sm text-red-700">
          {dispatch.error instanceof ApiError ? dispatch.error.message : "Não foi possível despachar o pedido."}
        </p>
      )}
      <Button type="button" size="sm" disabled={dispatch.isPending} onClick={() => dispatch.mutate()}>
        {dispatch.isPending ? "Enviando…" : "Despachar pedido iFood"}
      </Button>
    </div>
  );
}

export function IFoodKdsActions({ order, refresh }: { order: IFoodOrder; refresh: () => void }) {
  const confirmation = useIFoodConfirmation({ order, refresh });
  const ready = useMutation({
    mutationFn: () => api.post<{ ready_pending: boolean }>(`${endpoint}/${order.order_id}/ready`),
    onSuccess: refresh,
  });
  const inPreparation = order.state === "CONFIRMED" || order.state === "PREPARATION_STARTED";
  const readyPending = inPreparation && (order.ready_pending || ready.isSuccess);
  const status = readyPending ? "Aviso de pedido pronto enviado ao iFood. Aguardando retorno." : confirmation.state;
  return (
    <div className="space-y-2">
      <p role="status" className="text-sm font-semibold text-slate-700">
        {status}
      </p>
      <IFoodConfirmButton {...confirmation} />
      {inPreparation && ready.error && (ready.error instanceof ApiError && ready.error.status !== 401 && ready.error.status !== 403
        ? <p role="alert" className="text-red-700">{ready.error.message}</p>
        : <RequestErrorState error={ready.error} />)}
      {inPreparation && order.can_mark_ready && !readyPending && (
        <Button type="button" size="lg" disabled={ready.isPending} onClick={() => ready.mutate()}>
          {ready.isPending ? "Enviando…" : "Marcar pronto"}
        </Button>
      )}
      <IFoodDispatchAction order={order} refresh={refresh} />
    </div>
  );
}

export function ifoodScheduleLabel(order: IFoodOrder) {
  if (order.timing !== "SCHEDULED") return "";
  return order.scheduled_for && Number.isFinite(Date.parse(order.scheduled_for))
    ? `Agendado para ${dateTime.format(new Date(order.scheduled_for))}` : "Agendado";
}

const statusTone: Record<string, string> = {
  PLACED: "border-amber-200 bg-amber-50 text-amber-800",
  CONFIRMED: "border-sky-200 bg-sky-50 text-sky-800",
  PREPARATION_STARTED: "border-sky-200 bg-sky-50 text-sky-800",
  READY_TO_PICKUP: "border-emerald-200 bg-emerald-50 text-emerald-800",
  DISPATCHED: "border-orange-200 bg-orange-50 text-orange-800",
  DELIVERED: "border-emerald-200 bg-emerald-50 text-emerald-800",
  CONCLUDED: "border-emerald-200 bg-emerald-50 text-emerald-800",
  CANCELLED: "border-red-200 bg-red-50 text-red-800",
};

function IFoodCancellationForm({ orderId, refresh, close }: {
  orderId: string;
  refresh: () => void;
  close: () => void;
}) {
  const [reason, setReason] = useState("");
  const reasons = useQuery({
    queryKey: ["ifood-cancellation-reasons", orderId],
    queryFn: () => api.get<{ reasons: { code: string; description: string }[] }>(
      `${endpoint}/${orderId}/cancellation-reasons`,
    ),
    retry: false,
  });
  const cancel = useMutation({
    mutationFn: () => api.post(`${endpoint}/${orderId}/cancel`, { reason }),
    onSuccess: () => {
      refresh();
      close();
    },
    onError: () => { void reasons.refetch(); },
  });
  const available = reasons.data?.reasons ?? [];

  return (
    <form className="max-w-md space-y-3" onSubmit={(event) => {
      event.preventDefault();
      if (available.some((option) => option.code === reason) && !cancel.isPending) cancel.mutate();
    }}>
      {reasons.isPending && <p role="status">Consultando motivos no iFood…</p>}
      {reasons.isError && (
        <div className="space-y-2">
          <RequestErrorState error={reasons.error} />
          <Button type="button" size="sm" variant="outline" onClick={() => { void reasons.refetch(); }}>
            Consultar novamente
          </Button>
        </div>
      )}
      {reasons.isSuccess && available.length === 0 && <p>O iFood não disponibilizou motivos para este pedido.</p>}
      {available.length > 0 && (
        <label className="block space-y-1">
          <span>Motivo do cancelamento</span>
          <Select className="w-full" value={reason} disabled={cancel.isPending} onChange={(event) => setReason(event.target.value)}>
            <option value="">Selecione o motivo</option>
            {available.map((option) => <option key={option.code} value={option.code}>{option.description}</option>)}
          </Select>
        </label>
      )}
      {cancel.error && <p role="alert" className="text-red-700">
        {cancel.error instanceof ApiError ? cancel.error.message : "Não foi possível solicitar o cancelamento."}
      </p>}
      <div className="flex flex-wrap gap-2">
        {available.length > 0 && (
          <Button type="submit" size="sm" variant="destructive"
            disabled={cancel.isPending || reasons.isFetching || !available.some((option) => option.code === reason)}>
            {cancel.isPending ? "Enviando…" : "Enviar cancelamento ao iFood"}
          </Button>
        )}
        <Button type="button" size="sm" variant="outline" onClick={close} disabled={cancel.isPending}>Voltar</Button>
      </div>
    </form>
  );
}

function IFoodOrderRow({ order, refresh }: { order: IFoodOrder; refresh: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [cancellationOpen, setCancellationOpen] = useState(false);
  const detailsId = useId();
  const confirmation = useIFoodConfirmation({ order, refresh });
  const schedule = ifoodScheduleLabel(order);
  const createdAt = order.created_at && Number.isFinite(Date.parse(order.created_at))
    ? dateTime.format(new Date(order.created_at)) : "—";
  const payment = [...new Set(order.payment.map((entry) => [
    paymentMethods[entry.method] ?? entry.method,
    entry.type === "ONLINE" ? "pago online" : entry.type === "OFFLINE" ? "na entrega ou retirada" : "",
  ].filter(Boolean).join(" · ")))].filter(Boolean).join(", ");
  const delivery = order.delivered_by === "MERCHANT" ? "Entrega própria"
    : order.delivered_by === "IFOOD" ? "Entrega parceira"
    : orderTypes[order.order_type] ?? order.order_type;

  return (
    <>
      <TableRow className={cn("border-slate-100 hover:bg-brand-50/40", expanded && "bg-brand-50/60")}>
        <TableCell mobileLabel="Pedido" className="font-semibold text-slate-950">
          <div className="flex flex-wrap items-center gap-2">
            <span>#{order.display_id}</span>
            <Badge variant="outline" className="border-red-200 bg-red-50 px-2 py-0.5">
              <img src="/brand/ifood.svg" alt="iFood" width={28} height={15} />
            </Badge>
          </div>
        </TableCell>
        <TableCell mobileLabel="Data" className="whitespace-nowrap text-slate-600">{createdAt}</TableCell>
        <TableCell mobileLabel="Total" className="whitespace-nowrap font-semibold text-slate-950">{price.format(order.total)}</TableCell>
        <TableCell mobileLabel="Status">
          <Badge role="status" variant="outline" className={cn("px-2.5 py-1 font-medium", statusTone[order.state])}>
            {order.cancellation_status === "pending" ? "Aguardando cancelamento"
              : order.dispatch_pending ? "Aguardando despacho" : confirmation.state}
          </Badge>
          {order.cancellation_status === "rejected" && (
            <p className="mt-1 text-xs font-medium text-red-700">Cancelamento recusado pelo iFood</p>
          )}
        </TableCell>
        <TableCell mobileLabel="Entrega" className="text-slate-600">
          <p>{delivery}</p>
          {schedule && <p className="mt-1 text-xs">{schedule}</p>}
        </TableCell>
        <TableCell mobileLabel="Pagamento" className="break-words text-slate-600">{payment || "—"}</TableCell>
        <TableCell mobileLabel="Ações" mobileActions className="text-right">
          <Button type="button" size="sm" variant="outline" aria-expanded={expanded}
            aria-controls={expanded ? detailsId : undefined} onClick={() => setExpanded(!expanded)}>
            {expanded ? "Fechar" : "Detalhes"}
          </Button>
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow className="bg-slate-50 hover:bg-slate-50">
          <TableCell colSpan={7}>
            <section id={detailsId} aria-label={`Detalhes do pedido iFood ${order.display_id}`}
              className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 text-left text-sm">
              <p className="font-semibold text-slate-950">Itens e observações · #{order.display_id}</p>
              <IFoodItems items={order.items} />
              {order.observations && <p className="whitespace-pre-wrap break-words text-slate-600">{order.observations}</p>}
              <IFoodConfirmButton {...confirmation} />
              <IFoodDispatchAction order={order} refresh={refresh} />
              {order.can_cancel && (cancellationOpen ? (
                <IFoodCancellationForm orderId={order.order_id} refresh={refresh} close={() => setCancellationOpen(false)} />
              ) : (
                <Button type="button" size="sm" variant="outline" className="border-red-200 text-red-700"
                  onClick={() => setCancellationOpen(true)}>
                  Solicitar cancelamento
                </Button>
              ))}
            </section>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

export function useIFoodPilotOrders(tenantId?: number, kitchen = false) {
  return useQuery({
    enabled: Boolean(tenantId),
    queryKey: ["tenant", tenantId, "ifood-orders"],
    queryFn: () => api.get<{ enabled: boolean; confirmation_available?: boolean; pilot?: boolean; orders: IFoodOrder[] }>(endpoint),
    refetchInterval: (query) => query.state.data?.enabled ? (kitchen ? 5_000 : 15_000) : false,
    retry: false,
  });
}

export function IFoodPilotOrders({ tenantId }: { tenantId: number }) {
  const orders = useIFoodPilotOrders(tenantId);
  if (!orders.data?.enabled) return null;

  return (
    <Card>
      <CardHeader><CardTitle>{orders.data.pilot === false ? "Pedidos iFood" : "Pedidos iFood · Teste"}</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {orders.isError && <RequestErrorState error={orders.error} />}
        {!orders.data.confirmation_available && <p className="text-sm text-slate-600">Confirmação pelo painel indisponível.</p>}
        {!orders.data.orders.length && <p className="text-sm text-slate-600">{orders.data.pilot === false ? "Aguardando pedidos do iFood." : "Aguardando o primeiro pedido de teste."}</p>}
        {orders.data.orders.length > 0 && (
          <div className="min-w-0 overflow-hidden rounded-2xl lg:border lg:border-slate-200 lg:bg-white lg:shadow-sm">
            <Table mobileCards className="min-w-[880px]" containerClassName="max-w-full overflow-x-auto"
              aria-label="Lista de pedidos iFood">
              <TableHeader className="bg-slate-50">
                <TableRow>
                  <TableHead>Pedido</TableHead>
                  <TableHead>Data</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Entrega</TableHead>
                  <TableHead>Pagamento</TableHead>
                  <TableHead className="text-right">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {orders.data.orders.map((order) => (
                  <IFoodOrderRow key={order.order_id} order={order} refresh={() => { void orders.refetch(); }} />
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
