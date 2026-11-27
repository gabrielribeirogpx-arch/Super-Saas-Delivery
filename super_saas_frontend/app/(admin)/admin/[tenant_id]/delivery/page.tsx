"use client";

import { IFoodPartnerDeliveries } from "@/components/ifood-partner-deliveries";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Bike, Clock3, MapPin, Navigation2, Phone, Truck, UserRound } from "lucide-react";
import { AccessDenied } from "@/components/access-denied";
import { isForbiddenError } from "@/components/request-error-state";

import { DeliveryEtaBadge } from "@/components/delivery/DeliveryEtaBadge";
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

const STATUS_LABEL: Record<string, string> = {
  READY: "Pronto para entrega",
  PRONTO: "Pronto para entrega",
  OUT_FOR_DELIVERY: "Saiu para entrega",
  SAIU: "Saiu para entrega",
  SAIU_PARA_ENTREGA: "Saiu para entrega",
  DELIVERED: "Entregue",
  ENTREGUE: "Entregue",
};

function isOrderOutForDelivery(status: string): boolean {
  return ["OUT_FOR_DELIVERY", "SAIU", "SAIU_PARA_ENTREGA"].includes(status.toUpperCase());
}

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

  const label = `${isOrderOutForDelivery(order.status) ? "Em rota" : "Pronto"} há ${elapsed} min`;
  if (elapsed < 10) return { label, className: "bg-emerald-50 text-emerald-800" };
  if (elapsed <= 20) return { label, className: "bg-slate-100 text-slate-700" };
  return { label, className: "bg-red-50 text-red-700" };
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

  const inRouteCount = ordersQuery.data.filter((order) => isOrderOutForDelivery(order.status)).length;
  const readyCount = ordersQuery.data.length - inRouteCount;

  return (
    <div className="space-y-5 pb-6">
      <Card className="rounded-2xl border-slate-200/80 shadow-sm">
        <CardHeader className="space-y-0 p-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-5">
          <div className="flex items-center gap-3">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-red-50 text-red-600">
              <Truck className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <CardTitle className="text-lg font-bold text-slate-950">Entregas</CardTitle>
              <p className="mt-1 text-xs text-slate-500">Acompanhe os pedidos prontos e em rota.</p>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2 sm:mt-0" aria-label="Resumo das entregas">
            <span className="rounded-full bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700">{inRouteCount} em rota</span>
            <span className="rounded-full bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-800">{readyCount} prontos</span>
          </div>
        </CardHeader>
      </Card>

      {["owner", "admin", "operator", "cashier"].includes(currentUser?.role ?? "") && (
        <IFoodPartnerDeliveries key={tenantId} tenantId={tenantId} />
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {ordersQuery.data.length === 0 && (
          <Card className="rounded-2xl border-dashed border-slate-200 md:col-span-2 xl:col-span-3">
            <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
              <span className="grid h-12 w-12 place-items-center rounded-full bg-slate-100 text-slate-500"><Bike className="h-6 w-6" aria-hidden="true" /></span>
              <p className="font-semibold text-slate-900">Nenhuma entrega em andamento</p>
              <p className="text-sm text-slate-500">Os pedidos prontos e em rota aparecerão aqui.</p>
            </CardContent>
          </Card>
        )}

        {ordersQuery.data.map((order) => {
          const normalizedStatus = (order.status || "").toUpperCase();
          const statusLabel = STATUS_LABEL[normalizedStatus] ?? "Status indisponível";
          const isReady = normalizedStatus === "READY" || normalizedStatus === "PRONTO";
          const isOutForDelivery = isOrderOutForDelivery(order.status);
          const formattedAddress = formatAddress(order);
          const waitTimeBadge = getTimeBadge(order, nowMs);
          const phoneDigits = (order.cliente_telefone || "").replace(/\D/g, "");
          const startPending = startDeliveryMutation.isPending && startDeliveryMutation.variables === order.id;
          const completePending = completeDeliveryMutation.isPending && completeDeliveryMutation.variables === order.id;
          const actionError = startDeliveryMutation.isError && startDeliveryMutation.variables === order.id
            ? startDeliveryMutation.error
            : completeDeliveryMutation.isError && completeDeliveryMutation.variables === order.id
              ? completeDeliveryMutation.error
              : null;

          return (
            <Card key={order.id} className="flex h-full min-w-0 flex-col overflow-hidden rounded-2xl border-slate-200/80 shadow-sm transition-shadow hover:shadow-md">
              <div className={`h-1 w-full ${isOutForDelivery ? "bg-red-600" : "bg-amber-500"}`} aria-hidden="true" />
              <CardHeader className="space-y-0 p-5 pb-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-500">Pedido</p>
                    <CardTitle className="mt-1 text-2xl font-extrabold tracking-tight text-slate-950">#{order.daily_order_number ?? order.id}</CardTitle>
                  </div>
                  <span className={`inline-flex max-w-[55%] shrink-0 items-center rounded-full px-2.5 py-1 text-right text-xs font-bold leading-tight ${isOutForDelivery ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-800"}`}>
                    {statusLabel}
                  </span>
                </div>
                {waitTimeBadge && <span className={`mt-3 inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${waitTimeBadge.className}`}>
                  <Clock3 className="h-3.5 w-3.5" aria-hidden="true" />
                  {waitTimeBadge.label}
                </span>}
              </CardHeader>
              <CardContent className="flex flex-1 flex-col gap-4 px-5 pb-5 pt-0">
                {isOutForDelivery && <DeliveryEtaBadge orderId={order.id} />}

                <div className="flex min-w-0 items-start gap-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-600"><UserRound className="h-4 w-4" aria-hidden="true" /></span>
                  <div className="min-w-0">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Cliente</p>
                    <p className="truncate text-sm font-semibold text-slate-900" title={order.cliente_nome || undefined}>{order.cliente_nome || "Cliente"}</p>
                    {phoneDigits ? <a href={`tel:${phoneDigits}`} className="mt-0.5 inline-flex items-center gap-1 text-xs text-slate-600 underline-offset-2 hover:text-red-700 hover:underline">
                      <Phone className="h-3 w-3" aria-hidden="true" />{order.cliente_telefone}
                    </a> : <p className="mt-0.5 text-xs text-slate-500">Telefone não informado</p>}
                  </div>
                </div>

                <div className="flex min-w-0 items-start gap-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-600"><MapPin className="h-4 w-4" aria-hidden="true" /></span>
                  <div className="min-w-0">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Endereço de entrega</p>
                    <p className="mt-0.5 break-words text-sm leading-5 text-slate-800">{formattedAddress}</p>
                  </div>
                </div>

                {isOutForDelivery && (
                  <div className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-white text-red-600 shadow-sm"><Bike className="h-4 w-4" aria-hidden="true" /></span>
                    <div className="min-w-0">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Entregador</p>
                      <p className="truncate text-sm font-semibold text-slate-900">{order.assigned_delivery_user_name || (order.assigned_delivery_user_id ? `#${order.assigned_delivery_user_id}` : "Aguardando atribuição")}</p>
                    </div>
                  </div>
                )}

                <div className="mt-auto border-t border-slate-100 pt-4">
                  {isReady && <Button
                    className="h-11 w-full justify-center gap-2 bg-red-600 font-semibold text-white hover:bg-red-700"
                    onClick={() => startDeliveryMutation.mutate(order.id)}
                    disabled={startDeliveryMutation.isPending}
                  >
                    {startPending ? "Iniciando..." : "Iniciar entrega"}
                    {!startPending && <ArrowRight className="h-4 w-4" aria-hidden="true" />}
                  </Button>}
                  {isOutForDelivery && <div className="flex flex-col gap-2">
                    {order.tracking_token && <Button asChild className="h-11 w-full min-w-0 justify-center gap-2 bg-red-600 px-3 font-semibold text-white hover:bg-red-700">
                      <Link href={`/pedido/${encodeURIComponent(order.tracking_token)}`}>
                        <Navigation2 className="h-4 w-4 shrink-0" aria-hidden="true" />
                        <span>Acompanhar no mapa</span>
                      </Link>
                    </Button>}
                    <Button
                      className="h-11 w-full border-slate-200 px-3 font-semibold text-slate-700 hover:bg-slate-50"
                      variant="outline"
                      onClick={() => completeDeliveryMutation.mutate(order.id)}
                      disabled={completeDeliveryMutation.isPending}
                    >
                      {completePending ? "Concluindo..." : "Marcar entregue"}
                    </Button>
                  </div>}
                  {actionError && <p role="alert" className="mt-2 text-xs text-red-700">{actionError instanceof ApiError ? actionError.message : "Não foi possível atualizar o pedido. Tente novamente."}</p>}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
