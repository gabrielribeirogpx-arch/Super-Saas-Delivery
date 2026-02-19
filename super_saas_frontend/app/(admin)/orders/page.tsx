"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useSession } from "@/hooks/use-session";
import { api } from "@/lib/api";

interface Order {
  id: number;
  tenant_id: number;
  cliente_nome: string;
  cliente_telefone: string;
  itens: string | null;
  items_json?: unknown;
  endereco: string;
  observacao?: string;
  tipo_entrega: string;
  forma_pagamento: string;
  valor_total: number;
  total_cents?: number;
  status: string;
  created_at: string;
}

interface OrderItem {
  id: number;
  name: string;
  quantity: number;
  unit_price_cents: number;
  subtotal_cents: number;
  modifiers?: Array<{ name: string; price_cents?: number }>;
  production_area?: string;
}

const statusMap: Record<string, { label: string; variant: "default" | "secondary" | "warning" | "success" | "danger" }> = {
  RECEBIDO: { label: "Recebido", variant: "warning" },
  CONFIRMADO: { label: "Confirmado", variant: "default" },
  PREPARANDO: { label: "Preparando", variant: "secondary" },
  PRONTO: { label: "Pronto", variant: "success" },
  ENTREGUE: { label: "Entregue", variant: "success" },
  CANCELADO: { label: "Cancelado", variant: "danger" },
};

const statusOptions = ["RECEBIDO", "CONFIRMADO", "PREPARANDO", "PRONTO", "ENTREGUE", "CANCELADO"];

export default function OrdersPage() {
  const queryClient = useQueryClient();
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const { data: session, isLoading: isSessionLoading } = useSession();
  const tenantId = session?.tenant_id;

  const { data: orders, isLoading, isError } = useQuery({
    queryKey: ["orders", tenantId],
    queryFn: () => api.get<Order[]>(`/api/orders/${tenantId}`),
    enabled: Boolean(tenantId),
  });

  const orderItemsQuery = useQuery({
    queryKey: ["order-items", selectedOrderId],
    queryFn: () => api.get<OrderItem[]>(`/api/orders/${selectedOrderId}/items`),
    enabled: Boolean(selectedOrderId),
  });

  const updateStatus = useMutation({
    mutationFn: ({ orderId, status }: { orderId: number; status: string }) =>
      api.patch(`/api/orders/${orderId}/status`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      if (selectedOrderId) {
        queryClient.invalidateQueries({ queryKey: ["order-items", selectedOrderId] });
      }
    },
  });

  const selectedOrder = useMemo(
    () => orders?.find((order) => order.id === selectedOrderId),
    [orders, selectedOrderId]
  );

  if (isSessionLoading || isLoading) {
    return <p className="text-sm text-slate-500">Carregando pedidos...</p>;
  }

  if (!tenantId || isError || !orders) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
        Não foi possível carregar pedidos.
      </div>
    );
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      <Card>
        <CardHeader>
          <CardTitle>Pedidos</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Cliente</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Total</TableHead>
                <TableHead>Recebido em</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {orders.map((order) => {
                const status = statusMap[order.status] ?? {
                  label: order.status,
                  variant: "secondary" as const,
                };
                return (
                  <TableRow
                    key={order.id}
                    className="cursor-pointer"
                    onClick={() => setSelectedOrderId(order.id)}
                  >
                    <TableCell>#{order.id}</TableCell>
                    <TableCell>{order.cliente_nome}</TableCell>
                    <TableCell>
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </TableCell>
                    <TableCell>R$ {(order.valor_total / 100).toFixed(2)}</TableCell>
                    <TableCell>
                      {new Date(order.created_at).toLocaleString("pt-BR")}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Detalhes do pedido</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {!selectedOrder && (
            <p className="text-sm text-slate-500">Selecione um pedido na lista.</p>
          )}
          {selectedOrder && (
            <>
              <div>
                <p className="text-sm font-medium text-slate-900">
                  {selectedOrder.cliente_nome}
                </p>
                <p className="text-xs text-slate-500">{selectedOrder.cliente_telefone}</p>
                <p className="text-xs text-slate-500">{selectedOrder.endereco}</p>
                {selectedOrder.observacao && (
                  <p className="text-xs text-slate-500">Obs: {selectedOrder.observacao}</p>
                )}
              </div>
              <div className="space-y-2">
                <p className="text-sm font-semibold text-slate-700">Itens</p>
                {orderItemsQuery.isLoading && (
                  <p className="text-xs text-slate-500">Carregando itens...</p>
                )}
                {orderItemsQuery.data && (
                  <ul className="space-y-2 text-sm">
                    {orderItemsQuery.data.map((item) => (
                      <li key={item.id} className="rounded-lg border border-slate-200 p-3">
                        <div className="flex items-center justify-between">
                          <span>
                            {item.quantity}x {item.name}
                          </span>
                          <span>
                            R$ {(item.subtotal_cents / 100).toFixed(2)}
                          </span>
                        </div>
                        {item.modifiers && item.modifiers.length > 0 && (
                          <p className="text-xs text-slate-500">
                            {item.modifiers.map((mod) => mod.name).join(", ")}
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="space-y-2">
                <p className="text-sm font-semibold text-slate-700">Ações rápidas</p>
                <div className="flex flex-wrap gap-2">
                  {statusOptions.map((status) => (
                    <Button
                      key={status}
                      variant="outline"
                      size="sm"
                      onClick={() => updateStatus.mutate({ orderId: selectedOrder.id, status })}
                    >
                      {status}
                    </Button>
                  ))}
                </div>
                {updateStatus.isError && (
                  <p className="text-xs text-red-600">Erro ao atualizar status.</p>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
