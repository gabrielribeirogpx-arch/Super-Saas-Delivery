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

interface Item {
  name: string;
  quantity: number;
  observations?: string | null;
  options: Item[];
}

interface IFoodOrder {
  order_id: string;
  display_id: string;
  order_type: string;
  timing?: string;
  scheduled_for?: string;
  total: number;
  items: Item[];
  payment: { method: string; type: string }[];
  observations?: string;
  state: string;
  confirmation_pending: boolean;
  confirmation_deadline: string;
  can_confirm: boolean;
}

function OrderItems({ items }: { items: Item[] }) {
  return (
    <ul className="space-y-1 pl-4">
      {items.map((item, index) => (
        <li key={index} className="list-disc">
          {item.quantity}× {item.name}
          {item.observations && <p className="text-slate-600">{item.observations}</p>}
          {item.options.length > 0 && <OrderItems items={item.options} />}
        </li>
      ))}
    </ul>
  );
}

function PilotOrderCard({ order, refresh }: { order: IFoodOrder; refresh: () => void }) {
  const confirm = useMutation({
    mutationFn: () => api.post<{ confirmation_pending: boolean }>(`${endpoint}/${order.order_id}/confirm`),
    onSuccess: refresh,
  });
  const sent = order.state === "PLACED" && (order.confirmation_pending || confirm.isSuccess);
  const expired = Date.parse(order.confirmation_deadline) <= Date.now();
  const state = sent ? "Confirmação enviada ao iFood"
    : order.state === "PLACED" && expired ? "Prazo de confirmação encerrado"
    : states[order.state] ?? order.state;

  return (
    <article className="space-y-3 rounded-xl border border-slate-200 p-4 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-semibold text-slate-950">Pedido #{order.display_id} · iFood</p>
        <p role="status" className="font-medium text-slate-700">{state}</p>
      </div>
      <p>{orderTypes[order.order_type] ?? order.order_type} · {price.format(order.total)}</p>
      {order.timing === "SCHEDULED" && (
        <p>Agendado{order.scheduled_for && Number.isFinite(Date.parse(order.scheduled_for))
          ? ` para ${dateTime.format(new Date(order.scheduled_for))}` : ""}</p>
      )}
      {order.payment.length > 0 && <p>Pagamento {order.payment.map((entry) =>
        [paymentMethods[entry.method] ?? entry.method, entry.type === "ONLINE" ? "pago online"
          : entry.type === "OFFLINE" ? "na entrega ou retirada" : ""].filter(Boolean).join(" · "),
      ).join(", ")}</p>}
      <details className="space-y-2">
        <summary className="cursor-pointer font-medium text-slate-700">Itens e observações</summary>
        <OrderItems items={order.items} />
        {order.observations && <p className="text-slate-600">{order.observations}</p>}
      </details>
      {confirm.error && (confirm.error instanceof ApiError && confirm.error.status !== 401 && confirm.error.status !== 403
        ? <p role="alert" className="text-red-700">{confirm.error.message}</p>
        : <RequestErrorState error={confirm.error} />)}
      {order.can_confirm && !expired && !sent && (
        <Button type="button" size="sm" disabled={confirm.isPending} onClick={() => confirm.mutate()}>
          {confirm.isPending ? "Enviando…" : "Confirmar pedido iFood"}
        </Button>
      )}
    </article>
  );
}

export function IFoodPilotOrders({ tenantId }: { tenantId: number }) {
  const orders = useQuery({
    queryKey: ["tenant", tenantId, "ifood-orders"],
    queryFn: () => api.get<{ enabled: boolean; confirmation_available?: boolean; orders: IFoodOrder[] }>(endpoint),
    refetchInterval: (query) => query.state.data?.enabled ? 15_000 : false,
    retry: false,
  });

  if (!orders.data?.enabled) return null;
  return (
    <Card>
      <CardHeader><CardTitle>Pedidos iFood · Teste</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {orders.isError && <RequestErrorState error={orders.error} />}
        {!orders.data.confirmation_available && <p className="text-sm text-slate-600">Confirmação pelo painel indisponível.</p>}
        {!orders.data.orders.length && <p className="text-sm text-slate-600">Aguardando o primeiro pedido de teste.</p>}
        {orders.data.orders.map((order) => (
          <PilotOrderCard key={order.order_id} order={order} refresh={() => { void orders.refetch(); }} />
        ))}
      </CardContent>
    </Card>
  );
}
