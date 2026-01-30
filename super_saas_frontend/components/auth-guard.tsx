"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";

import { useSession } from "@/hooks/use-session";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isError, isLoading } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && isError) {
      const redirect = encodeURIComponent(pathname ?? "/");
      router.push(`/login?redirect=${redirect}`);
    }
  }, [isLoading, isError, router, pathname]);

  return <>{children}</>;
}
