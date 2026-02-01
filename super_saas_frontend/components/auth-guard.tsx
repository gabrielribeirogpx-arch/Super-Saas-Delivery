"use client";

import { useEffect } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";

import { getAdminAccessToken } from "@/lib/auth";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const isPublicTenantPage = pathname ? /^\/t\/[^/]+$/.test(pathname) : false;

  useEffect(() => {
    if (isPublicTenantPage) {
      return;
    }
    const token = getAdminAccessToken();
    console.log("AuthGuard token encontrado:", token);
    if (!token) {
      const currentPath = pathname ?? "/";
      const queryString = searchParams?.toString();
      const redirectValue = queryString ? `${currentPath}?${queryString}` : currentPath;
      const redirect = encodeURIComponent(redirectValue);
      router.push(`/login?redirect=${redirect}`);
    }
  }, [router, pathname, searchParams, isPublicTenantPage]);

  return <>{children}</>;
}
