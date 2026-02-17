"use client";

import { useEffect } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";

import { useSession } from "@/hooks/use-session";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { isLoading, isError } = useSession();
  const isPublicTenantPage = pathname ? /^\/t\/[^/]+$/.test(pathname) : false;

  useEffect(() => {
    if (isPublicTenantPage || isLoading || !isError) {
      return;
    }

    const currentPath = pathname ?? "/";
    const queryString = searchParams?.toString();
    const redirectValue = queryString ? `${currentPath}?${queryString}` : currentPath;
    const redirect = encodeURIComponent(redirectValue);
    router.push(`/login?redirect=${redirect}`);
  }, [router, pathname, searchParams, isPublicTenantPage, isLoading, isError]);

  return <>{children}</>;
}
