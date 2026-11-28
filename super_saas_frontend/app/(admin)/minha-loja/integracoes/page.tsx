"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ArrowUpRight, CircleAlert, CircleCheck, Link2, RefreshCw, ShoppingBag, Truck } from "lucide-react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RequestErrorState } from "@/components/request-error-state";
import { Card, CardContent } from "@/components/ui/card";
import { LoadingExperience } from "@/components/ui/loading-experience";
import { useSession } from "@/hooks/use-session";
import { api, ApiError } from "@/lib/api";

interface IFoodIntegrationStatus {
  last_event: { code: string; received_at: string } | null;
  production_available?: boolean;
  auto_accept_enabled?: boolean | null;
  connection_status?: "linked" | "expired" | "configured" | "configuration_required" | "unlinked" | null;
  environment?: "test" | "production" | null;
  merchant_id?: string | null;
  merchant_name?: string | null;
}

const dateTime = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
});

const integrationEndpoint = "/api/admin/store/integrations/ifood";

function ConnectIFood({ integration, refresh }: { integration: IFoodIntegrationStatus; refresh: () => void }) {
  const [code, setCode] = useState("");
  const [merchant, setMerchant] = useState(integration.merchant_id ?? "");
  const authorize = useMutation({
    mutationFn: () => api.post<{ url: string; challenge: string }>(`${integrationEndpoint}/authorize`),
  });
  const connect = useMutation({
    mutationFn: (payload: { challenge: string; authorization_code: string; merchant_id: string }) =>
      api.post(`${integrationEndpoint}/connect`, payload),
    onSuccess: () => {
      setCode("");
      authorize.reset();
      refresh();
    },
  });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (authorize.data) {
      connect.mutate({ challenge: authorize.data.challenge, authorization_code: code.trim(), merchant_id: merchant.trim() });
    }
  };
  const error = connect.error ?? authorize.error;
  return (
    <div className="space-y-3 border-t border-slate-200 pt-4">
      <Button type="button" variant={integration.merchant_id ? "outline" : "default"} disabled={authorize.isPending || connect.isPending}
        onClick={() => { connect.reset(); setCode(""); authorize.mutate(); }}>
        <Link2 className="mr-2 h-4 w-4" aria-hidden="true" />
        {authorize.isPending ? "Gerando link…" : integration.merchant_id ? "Renovar autorização" : "Conectar ao iFood"}
      </Button>
      {authorize.data && (
        <form className="max-w-lg space-y-4 rounded-xl border border-slate-200 bg-slate-50 p-4" onSubmit={submit}>
          <div className="space-y-2">
            <p className="text-sm font-semibold text-slate-950">Autorize o Fomizero no iFood</p>
            <p className="text-sm text-slate-600">Abra o Portal do Parceiro, selecione sua loja e permita a integração. Volte com o código que o iFood mostrar.</p>
            <Button asChild variant="outline" size="sm">
              <a href={authorize.data.url} target="_blank" rel="noopener noreferrer">
                Abrir autorização <ArrowUpRight className="ml-1 h-4 w-4" aria-hidden="true" />
              </a>
            </Button>
          </div>
          <label className="block space-y-1 text-sm">
            <span>Código de autorização do Portal do Parceiro</span>
            <input className="block w-full rounded-md border border-slate-300 p-2" required maxLength={128}
              value={code} onChange={(event) => setCode(event.target.value)} />
          </label>
          <label className="block space-y-1 text-sm">
            <span>UUID da loja iFood</span>
            <input className="block w-full rounded-md border border-slate-300 p-2" required maxLength={36}
              readOnly={Boolean(integration.merchant_id)} value={merchant} onChange={(event) => setMerchant(event.target.value)} />
          </label>
          <Button type="submit" size="sm" disabled={connect.isPending}>{connect.isPending ? "Conectando…" : "Vincular loja"}</Button>
        </form>
      )}
      {error && <p role="alert" className="text-sm text-red-700">{error instanceof ApiError ? error.message : "Não foi possível conectar ao iFood."}</p>}
    </div>
  );
}

function IFoodAutoAcceptSetting({ enabled, refresh }: { enabled: boolean; refresh: () => Promise<unknown> }) {
  const update = useMutation({
    mutationFn: (next: boolean) => api.patch(`${integrationEndpoint}/auto-accept`, { enabled: next }),
    onSuccess: refresh,
  });
  return (
    <section className="rounded-xl border border-slate-200 p-4">
      <label className="flex cursor-pointer items-start gap-3">
        <input type="checkbox" checked={enabled} disabled={update.isPending}
          className="mt-1 h-4 w-4 shrink-0 accent-red-600"
          onChange={(event) => update.mutate(event.target.checked)} />
        <span>
          <span className="block text-sm font-semibold text-slate-950">Aceitar pedidos automaticamente</span>
          <span className="mt-1 block text-sm text-slate-600">
            Novos pedidos do iFood ficam pendentes no KDS por cerca de 5 segundos antes do aceite automático. Ative quando a loja puder atender os pedidos que chegarem.
          </span>
        </span>
      </label>
      {update.isPending && <p role="status" className="mt-2 text-sm text-slate-600">Salvando preferência…</p>}
      {update.error && <p role="alert" className="mt-2 text-sm text-red-700">
        {update.error instanceof ApiError ? update.error.message : "Não foi possível salvar a preferência."}
      </p>}
    </section>
  );
}

export default function IntegrationsPage() {
  const { data: session } = useSession();
  const integration = useQuery({
    queryKey: ["tenant", session?.tenant_id, "ifood-integration"],
    queryFn: () => api.get<IFoodIntegrationStatus>(integrationEndpoint),
    enabled: Boolean(session?.tenant_id),
  });
  const status = integration.data?.connection_status ?? "unlinked";
  const environment = integration.data?.environment;
  const event = integration.data?.last_event;
  const connected = status === "linked" || status === "configured";
  const needsAttention = status === "expired" || status === "configuration_required";
  const StatusIcon = connected ? CircleCheck : needsAttention ? CircleAlert : Link2;
  const statusLabel = {
    linked: "Loja conectada",
    configured: "Piloto configurado",
    expired: "Autorização precisa de atenção",
    configuration_required: "Piloto precisa de configuração",
    unlinked: "Loja ainda não vinculada",
  }[status];
  const statusDescription = {
    linked: "A autorização desta loja está válida para a integração de pedidos.",
    configured: "Use um pedido de teste para verificar o recebimento no Fomizero.",
    expired: environment === "test"
      ? "Renove o token de teste para o piloto voltar a receber pedidos."
      : "Se a autorização continuar indisponível, renove a conexão pelo Portal do Parceiro.",
    configuration_required: "Finalize a configuração do piloto para habilitar o recebimento de pedidos de teste.",
    unlinked: integration.data?.production_available
      ? "Autorize o Fomizero no iFood para começar a receber pedidos desta loja."
      : "A conexão com o iFood ainda não está disponível para esta loja.",
  }[status];
  const eventLabels: Record<string, string> = {
    PLACED: "Pedido recebido", CONFIRMED: "Pedido confirmado",
    PREPARATION_STARTED: "Preparo iniciado", READY_TO_PICKUP: "Pronto para coleta",
    ASSIGN_DRIVER: "Entregador atribuído", DISPATCHED: "Saiu para entrega",
    DELIVERED: "Pedido entregue", CONCLUDED: "Pedido concluído",
    CANCELLED: "Pedido cancelado", CANCELLATION_REQUEST_FAILED: "Cancelamento recusado",
  };

  return (
    <div className="mx-auto w-full max-w-4xl space-y-5 px-4 py-2 sm:px-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Integrações</h1>
        <p className="mt-1 text-sm text-slate-600">Conecte sua loja e acompanhe o recebimento de pedidos.</p>
      </header>
      <Card className="overflow-hidden rounded-2xl border-slate-200 shadow-sm">
        <div className="flex flex-wrap items-center gap-4 border-b border-slate-200 bg-slate-50 px-5 py-5 sm:px-6">
          <span className="grid h-14 w-20 shrink-0 place-items-center rounded-xl border border-red-100 bg-white">
            <img src="/brand/ifood.svg" alt="" width={52} height={28} />
          </span>
          <div>
            <h2 className="text-lg font-semibold text-slate-950">iFood</h2>
            <p className="text-sm text-slate-600">Pedidos e entregas</p>
          </div>
          {environment && (
            <Badge variant="outline" className="sm:ml-auto">
              {environment === "test" ? "Ambiente de teste" : "Produção"}
            </Badge>
          )}
        </div>
        <CardContent className="space-y-5 p-5 sm:p-6">
          {integration.isPending ? (
            <LoadingExperience label="Consultando a integração do iFood" compact />
          ) : integration.isError ? (
            <RequestErrorState error={integration.error} />
          ) : (
            <>
              <div role="status" className={`flex items-start gap-3 rounded-xl border p-4 ${
                connected ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                  : needsAttention ? "border-amber-200 bg-amber-50 text-amber-950"
                  : "border-slate-200 bg-slate-50 text-slate-800"
              }`}>
                <StatusIcon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
                <div>
                  <p className="font-semibold">{statusLabel}</p>
                  <p className="mt-1 text-sm">{statusDescription}</p>
                </div>
              </div>
              {(integration.data?.merchant_id || event) && (
                <dl className="grid gap-4 text-sm sm:grid-cols-2">
                  {integration.data?.merchant_id && (
                    <div className="min-w-0 rounded-xl border border-slate-200 p-4">
                      <dt className="font-medium text-slate-600">Loja vinculada</dt>
                      <dd className="mt-1 font-semibold text-slate-950">
                        {integration.data.merchant_name || "Loja de teste iFood"}
                      </dd>
                      <dd className="mt-1 break-all text-xs text-slate-500">{integration.data.merchant_id}</dd>
                    </div>
                  )}
                  <div className="rounded-xl border border-slate-200 p-4">
                    <dt className="font-medium text-slate-600">Última atividade recebida</dt>
                    {event ? (
                      <>
                        <dd className="mt-1 font-semibold text-slate-950">{eventLabels[event.code] ?? "Atualização do iFood"}</dd>
                        <dd className="mt-1 text-xs text-slate-500">
                          <time dateTime={event.received_at}>{dateTime.format(new Date(event.received_at))}</time>
                        </dd>
                      </>
                    ) : <dd className="mt-1 text-slate-600">Nenhuma atividade recebida ainda.</dd>}
                  </div>
                </dl>
              )}
              {session?.role === "owner" && typeof integration.data?.auto_accept_enabled === "boolean" && (
                <IFoodAutoAcceptSetting key={`${session.tenant_id}-${integration.data.merchant_id}`}
                  enabled={integration.data.auto_accept_enabled} refresh={() => integration.refetch()} />
              )}
              {session?.role === "owner" && integration.data?.production_available && (
                <ConnectIFood key={`${session.tenant_id}-${integration.data.merchant_id ?? ""}`}
                  integration={integration.data} refresh={() => { void integration.refetch(); }} />
              )}
              <div className="flex flex-wrap gap-2 border-t border-slate-200 pt-4">
                {(integration.data?.merchant_id || event) && (
                  <>
                    <Button asChild variant="outline" size="sm">
                      <Link href="/orders"><ShoppingBag className="mr-2 h-4 w-4" aria-hidden="true" />Ver pedidos</Link>
                    </Button>
                    <Button asChild variant="outline" size="sm">
                      <Link href={`/admin/${session?.tenant_id}/delivery`}><Truck className="mr-2 h-4 w-4" aria-hidden="true" />Ver entregas</Link>
                    </Button>
                  </>
                )}
                {session?.role === "owner" && (
                  <Button asChild variant="outline" size="sm">
                    <a href="https://portal.ifood.com.br/services" target="_blank" rel="noopener noreferrer">
                      Opções de entrega no iFood <ArrowUpRight className="ml-1 h-4 w-4" aria-hidden="true" />
                    </a>
                  </Button>
                )}
                <Button type="button" variant="ghost" size="sm" disabled={integration.isFetching} onClick={() => { void integration.refetch(); }}>
                  <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />Atualizar status
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
