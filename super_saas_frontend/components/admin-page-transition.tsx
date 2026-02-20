"use client";

import { usePathname } from "next/navigation";

export function AdminPageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div
      key={pathname}
      className="h-full animate-[admin-page-enter_200ms_ease-out]"
    >
      {children}
    </div>
  );
}
