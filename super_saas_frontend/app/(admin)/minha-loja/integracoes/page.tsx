"use client";

import { useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { RequestErrorState } from "@/components/request-error-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingExperience } from "@/components/ui/loading-experience";
import { useSession } from "@/hooks/use-session";
import { api, ApiError } from "@/lib/api";

interface IFoodIntegrationStatus {
  last_event: { code: string; received_at: string } | null;
  production_available?: boolean;
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
      {integration.merchant_name && <p className="text-sm font-semibold">Loja conectada · {integration.merchant_name}</p>}
      <Button type="button" variant="outline" size="sm" disabled={authorize.isPending || connect.isPending}
        onClick={() => { connect.reset(); setCode(""); authorize.mutate(); }}>
        {authorize.isPending ? "Gerando link…" : integration.merchant_id ? "Renovar autorização" : "Conectar ao iFood"}
      </Button>
      {authorize.data && (
        <form className="max-w-md space-y-3" onSubmit={submit}>
          <a className="block text-sm font-semibold underline" href={authorize.data.url} target="_blank" rel="noopener noreferrer">
            Abrir autorização no Portal do Parceiro
          </a>
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

export default function IntegrationsPage() {
  const { data: session } = useSession();
  const integration = useQuery({
    queryKey: ["tenant", session?.tenant_id, "ifood-integration"],
    queryFn: () => api.get<IFoodIntegrationStatus>(integrationEndpoint),
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
                {integration.data?.production_available
                  ? "Após vincular a loja, os eventos do iFood aparecem aqui."
                  : "Após a configuração do piloto, um pedido de teste permite verificar o recebimento aqui."}
              </p>
            </div>
          )}
          {session?.role === "owner" && integration.data?.production_available && (
            <ConnectIFood key={`${session.tenant_id}-${integration.data.merchant_id ?? ""}`}
              integration={integration.data} refresh={() => { void integration.refetch(); }} />
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
            {integration.data?.production_available
              ? "Os pedidos recebidos aparecem na seção iFood da aba Pedidos."
              : "Os pedidos de teste importados aparecem na seção iFood da aba Pedidos."}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
