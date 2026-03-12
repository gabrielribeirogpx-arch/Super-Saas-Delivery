"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { t } from "@/i18n/translate";

export default function DriverLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="min-h-screen bg-gray-100 p-3">
      <div className="mx-auto max-w-md rounded-xl bg-white p-4 shadow">
        <header className="mb-4 flex items-center justify-between">
          <h1 className="text-lg font-bold">{title}</h1>
          <Link className="text-sm text-blue-600" href="/driver/dashboard">{t("dashboard")}</Link>
        </header>
        {children}
      </div>
    </main>
  );
}
