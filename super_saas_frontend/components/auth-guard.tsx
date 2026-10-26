"use client";

import { useEffect } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";

import { useSession } from "@/hooks/use-session";
import { RequestErrorState, classifyRequestError } from "@/components/request-error-state";
import { LoadingExperience } from "@/components/ui/loading-experience";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { error, isLoading, isError } = useSession();
  const isPublicTenantPage = pathname ? /^\/t\/[^/]+$/.test(pathname) : false;

  useEffect(() => {
    if (isPublicTenantPage || isLoading || !isError || classifyRequestError(error) !== "unauthenticated") {
      return;
    }

    const currentPath = pathname ?? "/";
    const queryString = searchParams?.toString();
    const redirectValue = queryString ? `${currentPath}?${queryString}` : currentPath;
    const redirect = encodeURIComponent(redirectValue);
    router.push(`/login?redirect=${redirect}`);
  }, [router, pathname, searchParams, isPublicTenantPage, isLoading, isError, error]);

  if (!isPublicTenantPage && isLoading) {
    return <div className="px-4"><LoadingExperience label="Preparando seu painel" /></div>;
  }

  if (!isPublicTenantPage && isError) {
    const kind = classifyRequestError(error);
    if (kind === "unauthenticated") return null;
    return <div className="p-6"><RequestErrorState error={error} /></div>;
  }

  return <>{children}</>;
}
