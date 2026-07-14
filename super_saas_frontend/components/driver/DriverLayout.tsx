"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ReactNode } from "react";
import { clearDriverSession } from "@/lib/driverAuth";
import { t } from "@/i18n/translate";

export default function DriverLayout({ title, children }: { title: string; children: ReactNode }) {
  const router = useRouter();
  const logout = () => {
    clearDriverSession();
    router.replace("/driver/login");
  };

  return (
    <main className="min-h-screen bg-gray-100 p-3">
      <div className="mx-auto max-w-md rounded-xl bg-white p-4 shadow">
        <header className="mb-4 flex items-center justify-between">
          <h1 className="text-lg font-bold">{title}</h1>
          <div className="flex items-center gap-3">
            <Link className="text-sm text-blue-600" href="/driver/dashboard">{t("dashboard")}</Link>
            <button type="button" className="text-sm font-semibold text-slate-600" onClick={logout}>Sair</button>
          </div>
        </header>
        {children}
      </div>
    </main>
  );
}
