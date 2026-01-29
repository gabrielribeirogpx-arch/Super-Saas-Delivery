"use client";

import { Badge } from "@/components/ui/badge";
import { useSession } from "@/hooks/use-session";

export function Topbar({ tenantId }: { tenantId: string }) {
  const { data, isLoading, isError } = useSession();

  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
      <div>
        <p className="text-xs uppercase text-slate-400">Tenant</p>
        <h1 className="text-lg font-semibold text-slate-900">
          Operação #{tenantId}
        </h1>
      </div>
      <div className="flex items-center gap-4">
        {isLoading && <Badge variant="secondary">Carregando sessão...</Badge>}
        {isError && <Badge variant="danger">Sessão expirada</Badge>}
        {data && (
          <div className="text-right">
            <p className="text-sm font-medium text-slate-900">{data.name}</p>
            <p className="text-xs text-slate-500">
              {data.email} · {data.role}
            </p>
          </div>
        )}
      </div>
    </header>
  );
}
