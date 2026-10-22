"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useSession } from "@/hooks/use-session";
import { PlanAccess } from "@/lib/planAccess";
import { isDeliveryRole } from "@/lib/authorization";

export function usePlanAccess() {
  const session = useSession();
  return useQuery({
    queryKey: ["plan-access", session.data?.tenant_id, session.data?.id],
    queryFn: () => api.get<PlanAccess>("/api/admin/billing/access"),
    enabled: Boolean(session.data && !isDeliveryRole(session.data.role)),
    staleTime: 10000, refetchInterval: 30000, retry: false,
  });
}
