"use client";

import { ReactNode, useEffect, useState } from "react";
import { hasDriverSession, redirectToDriverLogin } from "@/lib/driverAuth";

export default function DriverAuthGuard({ children }: { children: ReactNode }) {
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    if (!hasDriverSession()) {
      redirectToDriverLogin();
      return;
    }
    setAllowed(true);
  }, []);

  if (!allowed) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-100 p-4">
        <p className="rounded-xl bg-white p-4 text-sm font-medium text-slate-600 shadow">Redirecionando para o login...</p>
      </main>
    );
  }

  return children;
}
