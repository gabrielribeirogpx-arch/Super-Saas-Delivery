"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LoadingExperience } from "@/components/ui/loading-experience";
import { RequestErrorState } from "@/components/request-error-state";
import { api } from "@/lib/api";
import { buildTenantPublicUrl } from "@/lib/platformDomains";

interface TenantResponse {
  id: number;
  slug: string;
  manual_open_status: boolean;
  delivery_fee: number;
}

function parseDeliveryFee(value: string): number | null {
  const normalized = value.trim().replace(",", ".");
  if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) return null;
  const amount = Number(normalized);
  return Number.isFinite(amount) ? amount : null;
}

export default function MinhaLojaPage() {
  const [manualOpenStatus, setManualOpenStatus] = useState(true);
  const [deliveryFee, setDeliveryFee] = useState("0,00");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const storeQuery = useQuery({
    queryKey: ["tenant", "store-summary"],
    queryFn: () => api.get<TenantResponse>("/api/admin/store"),
  });

  useEffect(() => {
    if (!storeQuery.data) return;
    setManualOpenStatus(storeQuery.data.manual_open_status);
    setDeliveryFee((storeQuery.data.delivery_fee ?? 0).toFixed(2).replace(".", ","));
  }, [storeQuery.data]);

  const statusMutation = useMutation({
    mutationFn: (nextStatus: boolean) => api.patch<TenantResponse>("/api/admin/store/status", {
      manual_open_status: nextStatus,
    }),
    onSuccess: (updatedStore) => {
      setManualOpenStatus(updatedStore.manual_open_status);
      setStatusMessage(`Loja ${updatedStore.manual_open_status ? "aberta" : "fechada"} com sucesso.`);
    },
    onError: (_error, nextStatus) => {
      setManualOpenStatus(!nextStatus);
      setStatusMessage("Não foi possível atualizar o status da loja.");
    },
  });

  const feeMutation = useMutation({
    mutationFn: (amount: number) => api.patch<TenantResponse>("/api/admin/store", {
      delivery_fee: amount,
    }),
    onSuccess: (updatedStore) => {
      setDeliveryFee((updatedStore.delivery_fee ?? 0).toFixed(2).replace(".", ","));
      setStatusMessage("Taxa de entrega salva com sucesso.");
    },
    onError: () => setStatusMessage("Não foi possível salvar a taxa de entrega."),
  });

  if (storeQuery.isLoading) return <LoadingExperience label="Carregando sua loja" />;
  if (storeQuery.isError || !storeQuery.data) return <RequestErrorState error={storeQuery.error ?? new Error("Loja não encontrada")} />;

  const publicUrl = storeQuery.data.slug ? buildTenantPublicUrl(storeQuery.data.slug) : "";
  const parsedFee = parseDeliveryFee(deliveryFee);

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-2 sm:px-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-950">Operação da loja</h1>
        <p className="mt-1 text-sm text-slate-600">Controle a disponibilidade e a taxa de entrega. A identidade visual e o tempo exibido no cardápio ficam na Prévia do Cardápio.</p>
      </div>

      {statusMessage && <p role="status" className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">{statusMessage}</p>}

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="rounded-2xl border border-slate-200 shadow-sm">
          <CardHeader><CardTitle>Status da loja</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-slate-600">Feche a loja quando não puder receber novos pedidos.</p>
            <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm font-medium text-slate-900">
              <span className="switch">
                <input
                  type="checkbox"
                  role="switch"
                  checked={manualOpenStatus}
                  disabled={statusMutation.isPending}
                  onChange={(event) => {
                    const nextStatus = event.target.checked;
                    setManualOpenStatus(nextStatus);
                    setStatusMessage(null);
                    statusMutation.mutate(nextStatus);
                  }}
                />
                <span className="slider" />
              </span>
              <span>{manualOpenStatus ? "Aberta para pedidos" : "Fechada para pedidos"}</span>
            </label>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border border-slate-200 shadow-sm">
          <CardHeader><CardTitle>Taxa de entrega</CardTitle></CardHeader>
          <CardContent>
            <form className="space-y-3" onSubmit={(event) => {
              event.preventDefault();
              if (parsedFee === null) return;
              setStatusMessage(null);
              feeMutation.mutate(parsedFee);
            }}>
              <label htmlFor="deliveryFeeInput" className="block text-sm text-slate-600">Valor cobrado do cliente por entrega</label>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-slate-700">R$</span>
                <Input id="deliveryFeeInput" type="text" inputMode="decimal" value={deliveryFee} onChange={(event) => setDeliveryFee(event.target.value)} aria-invalid={parsedFee === null} className="max-w-40" />
              </div>
              {parsedFee === null && <p role="alert" className="text-xs text-red-600">Informe um valor válido, como 5,00.</p>}
              <Button type="submit" disabled={parsedFee === null || feeMutation.isPending}>{feeMutation.isPending ? "Salvando..." : "Salvar taxa"}</Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-2xl border border-slate-200 shadow-sm">
        <CardHeader><CardTitle>Cardápio público</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <p className="break-all rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">{publicUrl || "Endereço público indisponível."}</p>
          <div className="flex flex-wrap gap-2">
            {publicUrl && <Button asChild variant="outline"><a href={publicUrl} target="_blank" rel="noopener noreferrer">Abrir cardápio</a></Button>}
            <Button asChild><Link href="/storefront-preview">Editar na Prévia do Cardápio</Link></Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
