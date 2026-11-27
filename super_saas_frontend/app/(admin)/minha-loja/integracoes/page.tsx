"use client";

import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { RequestErrorState } from "@/components/request-error-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingExperience } from "@/components/ui/loading-experience";
import { useSession } from "@/hooks/use-session";
import { api } from "@/lib/api";

interface IFoodIntegrationStatus {
  last_event: { code: string; received_at: string } | null;
}

const dateTime = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
});

export default function IntegrationsPage() {
  const { data: session } = useSession();
  const integration = useQuery({
    queryKey: ["tenant", session?.tenant_id, "ifood-integration"],
    queryFn: () => api.get<IFoodIntegrationStatus>("/api/admin/store/integrations/ifood"),
    enabled: Boolean(session?.tenant_id),
  });
  const event = integration.data?.last_event;

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-2 sm:px-6">
      <h1 className="text-2xl font-semibold text-slate-950">Integrações</h1>
      <Card>
        <CardHeader>
          <CardTitle>iFood</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {integration.isPending ? (
            <LoadingExperience label="Consultando eventos do iFood" compact />
          ) : integration.isError ? (
            <RequestErrorState error={integration.error} />
          ) : event ? (
            <>
              <p className="text-sm font-semibold text-emerald-700">Recebimento registrado</p>
              <dl className="grid gap-4 rounded-lg bg-slate-50 p-4 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-slate-600">Último evento</dt>
                  <dd className="break-all font-medium text-slate-950">{event.code}</dd>
                </div>
                <div>
                  <dt className="text-slate-600">Recebido em</dt>
                  <dd className="font-medium text-slate-950">
                    <time dateTime={event.received_at}>{dateTime.format(new Date(event.received_at))}</time>
                  </dd>
                </div>
              </dl>
            </>
          ) : (
            <div>
              <p className="text-sm font-semibold text-slate-950">Aguardando primeiro evento</p>
              <p className="mt-1 text-sm text-slate-600">
                Após a configuração do piloto, um pedido de teste permite verificar o recebimento aqui.
              </p>
            </div>
          )}
          {session?.role === "owner" && (
            <div className="space-y-2 border-t border-slate-200 pt-4">
              <p className="text-sm text-slate-600">
                Escolha as modalidades de entrega disponíveis para sua loja no Portal do Parceiro.
              </p>
              <Button asChild variant="outline" size="sm">
                <a href="https://portal.ifood.com.br/services" target="_blank" rel="noopener noreferrer">
                  Ver opções de entrega no iFood
                </a>
              </Button>
            </div>
          )}
          <p className="text-sm text-slate-600">
            Os pedidos de teste importados aparecem na seção iFood da aba Pedidos.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
