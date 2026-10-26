"use client";
import { useSession } from "@/hooks/use-session";
import { isDeliveryRole } from "@/lib/authorization";
import { AccessDenied } from "@/components/access-denied";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePlanAccess } from "@/hooks/use-plan-access";
import { featureBlocked, routeFeature } from "@/lib/planAccess";
import { subscriptionFeatureNames } from "@/lib/subscriptions";

export function PlanAccessBoundary({ children }: { children: React.ReactNode }) {
  const path = usePathname() ?? "";
  const query = usePlanAccess();
  const feature = routeFeature(path);
  const session = useSession();
  if (feature && isDeliveryRole(session.data?.role)) return <AccessDenied backHref="/dashboard" />;
  if (feature && (query.isPending || query.isFetching && !query.data)) {
    return <p role="status">Conferindo acesso ao recurso...</p>;
  }
  if (feature && query.isError) {
    return <div role="alert" className="rounded-xl border bg-white p-6 space-y-3">
      <p>Não foi possível conferir seu plano.</p>
      <button onClick={() => query.refetch()} className="underline">Tentar novamente</button>
    </div>;
  }
  if (featureBlocked(query.data, feature)) {
    return <div className="rounded-xl border bg-white p-6 space-y-3" role="alert">
      <h1 className="text-xl font-semibold">{subscriptionFeatureNames[feature!] ?? "Recurso"}</h1>
      <p>{query.data?.active ? "Seu plano não inclui este recurso." : "Regularize sua assinatura para usar este recurso."}</p>
      <Link className="inline-block rounded-lg bg-red-600 px-4 py-2 text-white" href="/subscriptions">Ver planos e assinatura</Link>
    </div>;
  }
  const inactive = query.data?.managed && !query.data.active;
  return <>
    {inactive && !path.startsWith("/subscriptions") && <div role="status" className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
      Sua assinatura precisa ser regularizada. Novos pedidos e recursos pagos estão bloqueados. Histórico e financeiro continuam disponíveis.{" "}
      <Link href="/subscriptions" className="font-semibold underline">Ver assinatura</Link>
    </div>}
    {children}
  </>;
}
