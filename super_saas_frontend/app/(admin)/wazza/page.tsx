"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { WazzaOrderReviews } from "@/components/wazza-order-reviews";
import { Button } from "@/components/ui/button";
import { useSession } from "@/hooks/use-session";
import { api } from "@/lib/api";

const statuses = {
  disabled: "Integração desativada",
  setup_required: "Configuração pendente no Fomizero",
  awaiting_contact: "Aguardando primeiro contato do Wazza",
  contact_verified: "Comunicação com o Wazza verificada",
};

export default function WazzaPage() {
  const { data: session } = useSession();
  const tenantId = session?.tenant_id;
  const connection = useQuery({
    queryKey: ["wazza-connection", tenantId],
    queryFn: () => api.get<{ state: keyof typeof statuses; last_contact: string | null }>(
      `/api/orders/wazza/requests/connection?tenant_id=${tenantId}`,
    ),
    enabled: Boolean(tenantId),
  });

  return (
    <div className="min-w-0 space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Wazza</h1>
        <p className="mt-1 text-sm text-slate-600">Configure o WhatsApp da sua loja e acompanhe as solicitações dos clientes.</p>
      </header>
      <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 sm:p-6">
        <h2 className="text-lg font-semibold">Estado da integração</h2>
        <p role="status">
          {connection.data ? statuses[connection.data.state] :
            connection.isError ? "Não foi possível consultar o estado da integração." : "Consultando integração…"}
        </p>
        {connection.data?.last_contact && <p className="text-sm text-slate-600">
          Último contato registrado em {new Date(connection.data.last_contact).toLocaleString("pt-BR")}
        </p>}
        <Button variant="outline" disabled={!tenantId || connection.isFetching} onClick={() => void connection.refetch()}>
          Verificar conexão
        </Button>
      </section>
      <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4 sm:p-6">
        <h2 className="text-lg font-semibold">Conectar WhatsApp</h2>
        <ol className="list-decimal space-y-4 pl-5 text-sm">
          <li><strong>Vincule o número no Wazza.</strong> Abra o Wazza, entre na conta da loja e vincule o número que atenderá os clientes.</li>
          <li><strong>Verifique a comunicação.</strong> Se a configuração estiver pendente, peça à equipe responsável pela integração para concluir a conexão da sua loja. Depois, volte e selecione Verificar conexão.</li>
          <li><strong>Faça um pedido de teste em homologação.</strong> Envie uma mensagem ao número de teste, confirme o resumo pelo WhatsApp e confira o resultado em Pedidos.</li>
        </ol>
        <div className="flex flex-wrap gap-2">
          <Button asChild><a href="https://app.wazzaapi.com.br/" target="_blank" rel="noopener noreferrer">Abrir Wazza para vincular o número</a></Button>
          <Button asChild variant="outline"><Link href="/orders">Ver pedidos</Link></Button>
        </div>
      </section>
      {tenantId && <WazzaOrderReviews key={tenantId} tenantId={tenantId} onDecision={() => undefined} />}
    </div>
  );
}
