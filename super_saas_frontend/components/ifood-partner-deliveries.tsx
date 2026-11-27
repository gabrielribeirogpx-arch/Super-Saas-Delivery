"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { RequestErrorState } from "@/components/request-error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

const endpoint = "/api/admin/ifood-orders";
const localTime = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });
const deliveryStatuses: Record<string, string> = {
  CONFIRMED: "Pedido confirmado",
  PREPARATION_STARTED: "Em preparo",
  READY_TO_PICKUP: "Aguardando coleta",
  DISPATCHED: "Saiu para entrega",
  DELIVERED: "Entregue",
  CONCLUDED: "Concluído",
  CANCELLED: "Cancelado",
};

interface PartnerDelivery {
  order_id: string;
  display_id: string;
  state: string;
  driver_assigned: boolean;
  can_track: boolean;
}

interface Tracking {
  latitude?: number;
  longitude?: number;
  expectedDelivery?: string;
  trackDate?: string;
}

function DeliveryTracking({ tenantId, orderId }: { tenantId: number; orderId: string }) {
  const query = useQuery({
    queryKey: ["tenant", tenantId, "ifood-tracking", orderId],
    queryFn: () => api.get<{ tracking: Tracking | null }>(`${endpoint}/${orderId}/tracking`),
    refetchInterval: 30_000,
    staleTime: 30_000,
    retry: false,
  });
  const tracking = query.data?.tracking;
  if (query.isPending) return <p role="status">Consultando localização…</p>;
  if (query.isError || !tracking) return <p role="status">Localização ainda indisponível no iFood.</p>;

  const hasLocation = typeof tracking.latitude === "number" && typeof tracking.longitude === "number";
  const coordinates = encodeURIComponent(`${tracking.latitude},${tracking.longitude}`);
  return (
    <div className="space-y-2">
      {tracking.expectedDelivery && <p>Previsão de entrega {localTime.format(new Date(tracking.expectedDelivery))}</p>}
      {tracking.trackDate && <p>Última posição em {localTime.format(new Date(tracking.trackDate))}</p>}
      {hasLocation && (
        <Button asChild variant="outline" size="sm">
          <a href={`https://www.google.com/maps/search/?api=1&query=${coordinates}`} target="_blank" rel="noopener noreferrer">
            Ver localização no mapa
          </a>
        </Button>
      )}
    </div>
  );
}

function PartnerDeliveryCard({ tenantId, delivery }: { tenantId: number; delivery: PartnerDelivery }) {
  const [trackingOpen, setTrackingOpen] = useState(false);
  return (
    <article className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold text-slate-950">Pedido #{delivery.display_id}</h3>
        <Badge className="border-red-200 bg-red-50 text-red-700" variant="outline">Entrega parceira iFood</Badge>
      </div>
      <p role="status" className="font-semibold">{deliveryStatuses[delivery.state] ?? "Status indisponível"}</p>
      {delivery.can_track && (
        <>
          {delivery.driver_assigned && <p>Entregador atribuído</p>}
          <Button type="button" variant="outline" size="sm" aria-expanded={trackingOpen}
            onClick={() => setTrackingOpen((open) => !open)}>
            {trackingOpen ? "Ocultar rastreamento" : "Acompanhar entregador"}
          </Button>
          {trackingOpen && <DeliveryTracking tenantId={tenantId} orderId={delivery.order_id} />}
        </>
      )}
    </article>
  );
}

export function IFoodPartnerDeliveries({ tenantId }: { tenantId: number }) {
  const orders = useQuery({
    queryKey: ["tenant", tenantId, "ifood-partner-deliveries"],
    queryFn: () => api.get<{ enabled: boolean; deliveries: PartnerDelivery[] }>(`${endpoint}/deliveries`),
    refetchInterval: (query) => query.state.data?.enabled ? 10_000 : false,
    retry: false,
  });
  if (orders.isError) return <RequestErrorState error={orders.error} />;
  if (!orders.data?.enabled) return null;

  return (
    <Card>
      <CardHeader><CardTitle>Entregas parceiras iFood</CardTitle></CardHeader>
      <CardContent>
        {orders.data.deliveries.length === 0 ? (
          <p className="text-sm text-slate-600">Nenhuma entrega parceira do iFood registrada.</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {orders.data.deliveries.map((delivery) => (
              <PartnerDeliveryCard key={delivery.order_id} tenantId={tenantId} delivery={delivery} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
