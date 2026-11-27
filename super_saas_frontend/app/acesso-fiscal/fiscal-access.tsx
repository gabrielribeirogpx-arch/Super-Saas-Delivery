"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { FocusSetup } from "../(admin)/minha-loja/fiscal/focus-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";

interface AccessStatus {
  cnpj: string;
  legal_name: string;
  connected: boolean;
  available: boolean;
}

function DelegatedSetup({ token }: { token: string }) {
  const endpoint = window.location.origin + "/api/fiscal-delegation";
  const headers = { "X-Fiscal-Access": token };
  const status = useQuery({
    queryKey: ["fiscal-delegation"],
    queryFn: () => api.get<AccessStatus>(endpoint, headers),
    retry: false,
    gcTime: 0,
  });

  if (status.isPending) return <p role="status">Verificando acesso…</p>;
  if (status.isError) {
    const expired = status.error instanceof ApiError && status.error.status === 401;
    return <p role="alert">{expired
      ? "Este acesso expirou ou foi revogado. Peça um novo link ao restaurante."
      : "Não foi possível consultar o acesso fiscal."}</p>;
  }
  return (
    <div className="space-y-4">
      <p className="text-sm">{status.data.legal_name} · CNPJ {status.data.cnpj}</p>
      <FocusSetup {...status.data} endpoint={endpoint} headers={headers}
        onConnected={() => { void status.refetch(); }} />
    </div>
  );
}

export function FiscalAccess() {
  const [token, setToken] = useState<string | null>(null);
  useEffect(() => {
    const fragment = window.location.hash.slice(1);
    if (fragment) {
      window.history.replaceState(window.history.state, "", window.location.pathname);
      setToken(/^[A-Za-z0-9_-]{43}$/.test(fragment) ? fragment : "");
    } else {
      setToken((current) => current ?? "");
    }
  }, []);
  return (
    <main className="mx-auto w-full max-w-3xl p-4 sm:p-8">
      <Card>
        <CardHeader><CardTitle>Acesso fiscal do contador</CardTitle></CardHeader>
        <CardContent>
          {token === null ? <p role="status">Abrindo acesso fiscal…</p>
            : token ? <DelegatedSetup token={token} />
            : <p role="alert">Abra o link de acesso fiscal enviado pelo restaurante.</p>}
        </CardContent>
      </Card>
    </main>
  );
}
