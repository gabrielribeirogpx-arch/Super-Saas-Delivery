"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { RequestErrorState } from "@/components/request-error-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";

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
    </div>
  );
}

export function ifoodScheduleLabel(order: IFoodOrder) {
  if (order.timing !== "SCHEDULED") return "";
  return order.scheduled_for && Number.isFinite(Date.parse(order.scheduled_for))
    ? `Agendado para ${dateTime.format(new Date(order.scheduled_for))}` : "Agendado";
}

function PilotOrderCard({ order, refresh }: { order: IFoodOrder; refresh: () => void }) {
  const confirmation = useIFoodConfirmation({ order, refresh });
  const schedule = ifoodScheduleLabel(order);
  return (
    <article className="space-y-3 rounded-xl border border-slate-200 p-4 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-semibold text-slate-950">Pedido #{order.display_id} · iFood</p>
        <p role="status" className="font-medium text-slate-700">{confirmation.state}</p>
      </div>
      <p>{orderTypes[order.order_type] ?? order.order_type} · {price.format(order.total)}</p>
      {schedule && <p>{schedule}</p>}
      {order.payment.length > 0 && <p>Pagamento {order.payment.map((entry) =>
        [paymentMethods[entry.method] ?? entry.method, entry.type === "ONLINE" ? "pago online"
          : entry.type === "OFFLINE" ? "na entrega ou retirada" : ""].filter(Boolean).join(" · "),
      ).join(", ")}</p>}
      <details className="space-y-2">
        <summary className="cursor-pointer font-medium text-slate-700">Itens e observações</summary>
        <IFoodItems items={order.items} />
        {order.observations && <p className="text-slate-600">{order.observations}</p>}
      </details>
      <IFoodConfirmButton {...confirmation} />
    </article>
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
        {orders.data.orders.map((order) => (
          <PilotOrderCard key={order.order_id} order={order} refresh={() => { void orders.refetch(); }} />
        ))}
      </CardContent>
    </Card>
  );
}
