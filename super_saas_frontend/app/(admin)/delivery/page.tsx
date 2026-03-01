"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSession } from "@/hooks/use-session";
import { api } from "@/lib/api";

interface DeliveryAddress {
  street?: string | null;
  number?: string | null;
  neighborhood?: string | null;
  complement?: string | null;
}

interface DeliveryOrder {
  id: number;
  status: string;
  cliente_nome: string;
  cliente_telefone: string;
  endereco: string;
  ready_at?: string | null;
  out_for_delivery_at?: string | null;
  start_delivery_at?: string | null;
  delivery_address?: DeliveryAddress | null;
}

const STATUS_LABEL: Record<string, { label: string; variant: "warning" | "secondary" | "success" }> = {
  READY: { label: "Pronto", variant: "warning" },
  PRONTO: { label: "Pronto", variant: "warning" },
  OUT_FOR_DELIVERY: { label: "Saiu para entrega", variant: "secondary" },
  SAIU: { label: "Saiu para entrega", variant: "secondary" },
  SAIU_PARA_ENTREGA: { label: "Saiu para entrega", variant: "secondary" },
  DELIVERED: { label: "Entregue", variant: "success" },
  ENTREGUE: { label: "Entregue", variant: "success" },
};

function formatAddress(order: DeliveryOrder): string {
  const address = order.delivery_address;
  if (!address) return order.endereco || "Não informado";

  const street = (address.street ?? "").trim();
  const number = (address.number ?? "").trim();
  const neighborhood = (address.neighborhood ?? "").trim();
  const complement = (address.complement ?? "").trim();

  const streetWithNumber = [street, number].filter(Boolean).join(", ");
  const streetSection = streetWithNumber || street;

  const locationSection = [streetSection, neighborhood].filter(Boolean).join(" – ");
  const completeAddress = [locationSection, complement].filter(Boolean).join(" • ");

  return completeAddress || order.endereco || "Não informado";
}

function getElapsedMinutesFrom(referenceDate: string | null | undefined, nowMs: number): number | null {
  if (!referenceDate) return null;

  const parsed = new Date(referenceDate).getTime();
  if (Number.isNaN(parsed) || parsed > nowMs) return 0;

  return Math.floor((nowMs - parsed) / 60000);
}

function getTimeBadge(order: DeliveryOrder, nowMs: number): { label: string; className: string } | null {
  const upperStatus = (order.status || "").toUpperCase();

  const reference = upperStatus === "OUT_FOR_DELIVERY" || upperStatus === "SAIU" || upperStatus === "SAIU_PARA_ENTREGA"
    ? order.out_for_delivery_at ?? order.start_delivery_at
    : upperStatus === "READY" || upperStatus === "PRONTO"
      ? order.ready_at
      : null;

  const elapsed = getElapsedMinutesFrom(reference, nowMs);
  if (elapsed === null) return null;

  if (elapsed < 10) {
    return { label: `${elapsed} min`, className: "border-green-200 bg-green-100 text-green-800" };
  }
  if (elapsed <= 20) {
    return { label: `${elapsed} min`, className: "border-amber-200 bg-amber-100 text-amber-800" };
  }
  return { label: `${elapsed} min`, className: "border-red-200 bg-red-100 text-red-800" };
}

export default function DeliveryPage() {
  const queryClient = useQueryClient();
  const { data: session, isLoading: isSessionLoading } = useSession();
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNowMs(Date.now());
    }, 30000);

    return () => window.clearInterval(timer);
  }, []);

  const ordersQuery = useQuery({
    queryKey: ["delivery-orders", session?.tenant_id],
    queryFn: () => api.get<DeliveryOrder[]>("/api/delivery/orders?status=READY,OUT_FOR_DELIVERY"),
    enabled: Boolean(session?.tenant_id),
    refetchInterval: 10000,
  });

  const startDeliveryMutation = useMutation({
    mutationFn: (orderId: number) => api.patch(`/api/orders/${orderId}/start-delivery`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["delivery-orders"] });
    },
  });

  const completeDeliveryMutation = useMutation({
    mutationFn: (orderId: number) => api.patch(`/api/orders/${orderId}/complete-delivery`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["delivery-orders"] });
    },
  });

  if (isSessionLoading || ordersQuery.isLoading) {
    return <p className="text-sm text-slate-500">Carregando pedidos de entrega...</p>;
  }

  if (ordersQuery.isError || !ordersQuery.data) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
        Não foi possível carregar os pedidos de entrega.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Entregas</h1>
        <p className="text-sm text-slate-500">Pedidos prontos e em rota de entrega.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {ordersQuery.data.length === 0 && (
          <Card>
            <CardContent className="pt-6 text-sm text-slate-500">
              Nenhum pedido aguardando entrega.
            </CardContent>
          </Card>
        )}

        {ordersQuery.data.map((order) => {
          const status = STATUS_LABEL[order.status] ?? {
            label: order.status,
            variant: "secondary" as const,
          };
          const isReady = order.status === "READY" || order.status === "PRONTO";
          const isOutForDelivery =
            order.status === "OUT_FOR_DELIVERY" ||
            order.status === "SAIU" ||
            order.status === "SAIU_PARA_ENTREGA";
          const formattedAddress = formatAddress(order);
          const waitTimeBadge = getTimeBadge(order, nowMs);

          return (
            <Card key={order.id}>
              <CardHeader className="space-y-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Pedido #{order.id}</CardTitle>
                  <div className="flex items-center gap-2">
                    {waitTimeBadge && (
                      <Badge className={waitTimeBadge.className} variant="outline">
                        {waitTimeBadge.label}
                      </Badge>
                    )}
                    <Badge variant={status.variant}>{status.label}</Badge>
                  </div>
                </div>
                <div className="text-sm text-slate-600">
                  <p className="font-medium text-slate-900">{order.cliente_nome || "Cliente"}</p>
                  <p>{order.cliente_telefone || "Telefone não informado"}</p>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-xs font-semibold uppercase text-slate-500">Endereço</p>
                  <p className="text-sm text-slate-700">{formattedAddress}</p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    onClick={() => startDeliveryMutation.mutate(order.id)}
                    disabled={!isReady || startDeliveryMutation.isPending}
                  >
                    Iniciar entrega
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => completeDeliveryMutation.mutate(order.id)}
                    disabled={!isOutForDelivery || completeDeliveryMutation.isPending}
                  >
                    Entregue
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
