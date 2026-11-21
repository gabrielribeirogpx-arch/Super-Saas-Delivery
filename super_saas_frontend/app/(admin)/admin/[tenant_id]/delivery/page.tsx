"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bike, MapPin } from "lucide-react";
import { AccessDenied } from "@/components/access-denied";
import { isForbiddenError } from "@/components/request-error-state";

import { DeliveryEtaBadge } from "@/components/delivery/DeliveryEtaBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LoadingExperience } from "@/components/ui/loading-experience";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api";
import { authApi } from "@/lib/auth";

interface DeliveryAddress {
  street?: string | null;
  number?: string | null;
  neighborhood?: string | null;
  complement?: string | null;
}

interface DeliveryOrder {
  id: number;
  daily_order_number?: number | null;
  status: string;
  cliente_nome: string;
  cliente_telefone: string;
  endereco: string;
  ready_at?: string | null;
  out_for_delivery_at?: string | null;
  start_delivery_at?: string | null;
  delivery_address?: DeliveryAddress | null;
  assigned_delivery_user_id?: number | null;
  assigned_delivery_user_name?: string | null;
  tracking_token?: string | null;
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

  const reference =
    upperStatus === "OUT_FOR_DELIVERY" || upperStatus === "SAIU" || upperStatus === "SAIU_PARA_ENTREGA"
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
    return { label: `${elapsed} min`, className: "border-slate-200 bg-slate-100 text-slate-800" };
  }
  return { label: `${elapsed} min`, className: "border-red-200 bg-red-100 text-red-800" };
}

export default function AdminDeliveryPage() {
  const params = useParams<{ tenant_id: string }>();
  const queryClient = useQueryClient();
  const [nowMs, setNowMs] = useState(() => Date.now());

  const tenantId = useMemo(() => {
    const parsed = Number(params.tenant_id);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [params.tenant_id]);

  const { data: currentUser, isLoading: meLoading } = useQuery({
    queryKey: ["admin-auth-me"],
    queryFn: () => authApi.me(),
  });

  const tenantMismatch =
    tenantId !== null &&
    currentUser?.tenant_id !== undefined &&
    Number(currentUser.tenant_id) !== Number(tenantId);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNowMs(Date.now());
    }, 30000);

    return () => window.clearInterval(timer);
  }, []);

  const ordersQuery = useQuery({
    queryKey: ["tenant-delivery-orders", tenantId],
    queryFn: () => api.get<DeliveryOrder[]>("/api/delivery/orders?status=READY,OUT_FOR_DELIVERY"),
    enabled: tenantId !== null && !tenantMismatch,
    refetchInterval: 10000,
  });

  const startDeliveryMutation = useMutation({
    mutationFn: (orderId: number) => api.patch(`/api/orders/${orderId}/start-delivery`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant-delivery-orders", tenantId] });
    },
  });

  const completeDeliveryMutation = useMutation({
    mutationFn: (orderId: number) => api.patch(`/api/orders/${orderId}/complete-delivery`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant-delivery-orders", tenantId] });
    },
  });

  if (meLoading || ordersQuery.isLoading) {
    return <LoadingExperience label="Preparando as entregas" />;
  }

  if (tenantId === null) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
        Não foi possível identificar a loja.
      </div>
    );
  }

  if (tenantMismatch) {
    return <AccessDenied />;
  }

  if (isForbiddenError(ordersQuery.error)) return <AccessDenied />;

  if (ordersQuery.isError || !ordersQuery.data) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
        {ordersQuery.error instanceof ApiError
          ? ordersQuery.error.message
          : "Não foi possível carregar os pedidos de entrega."}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Entregas</CardTitle>
        </CardHeader>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {ordersQuery.data.length === 0 && (
          <Card>
            <CardContent className="pt-6 text-sm text-slate-500">Nenhum pedido aguardando entrega.</CardContent>
          </Card>
        )}

        {ordersQuery.data.map((order) => {
          const status = STATUS_LABEL[order.status] ?? {
            label: "Status indisponível",
            variant: "secondary" as const,
          };
          const isReady = order.status === "READY" || order.status === "PRONTO";
          const isOutForDeliveryExact = order.status === "OUT_FOR_DELIVERY";
          const isOutForDelivery =
            order.status === "OUT_FOR_DELIVERY" || order.status === "SAIU" || order.status === "SAIU_PARA_ENTREGA";
          const formattedAddress = formatAddress(order);
          const waitTimeBadge = getTimeBadge(order, nowMs);

          return (
            <Card key={order.id}>
              <CardHeader className="space-y-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Pedido #{order.daily_order_number ?? order.id}</CardTitle>
                  <div className="flex items-center gap-2">
                    {isOutForDeliveryExact && <DeliveryEtaBadge orderId={order.id} />}
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

                {isOutForDelivery && (
                  <div className="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2.5 text-sm text-slate-700">
                    <Bike className="h-4 w-4 shrink-0 text-red-600" aria-hidden="true" />
                    <span>Entregador: <strong className="text-slate-900">{order.assigned_delivery_user_name || (order.assigned_delivery_user_id ? `#${order.assigned_delivery_user_id}` : "Aguardando atribuição")}</strong></span>
                  </div>
                )}

                <div className="flex flex-wrap gap-2">
                  {isReady && <Button
                    size="sm"
                    onClick={() => startDeliveryMutation.mutate(order.id)}
                    disabled={startDeliveryMutation.isPending}
                  >
                    Iniciar entrega
                  </Button>}
                  {isOutForDelivery && order.tracking_token && <Button asChild size="sm">
                    <Link href={`/pedido/${encodeURIComponent(order.tracking_token)}`}>
                      <MapPin className="mr-1.5 h-4 w-4" aria-hidden="true" />
                      Acompanhar no mapa
                    </Link>
                  </Button>}
                  {isOutForDelivery && <Button
                    size="sm"
                    variant="outline"
                    onClick={() => completeDeliveryMutation.mutate(order.id)}
                    disabled={completeDeliveryMutation.isPending}
                  >
                    Entregue
                  </Button>}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
