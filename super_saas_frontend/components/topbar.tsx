"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Menu, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { authApi } from "@/lib/auth";
import { sidebarItems } from "@/components/sidebar";
import { useSession } from "@/hooks/use-session";

export function Topbar({ tenantId }: { tenantId: string }) {
  const { data, isLoading, isError } = useSession();
  const [isOpen, setIsOpen] = useState(false);
  const router = useRouter();

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } finally {
      router.push("/login");
    }
  };

  return (
    <header className="relative border-b border-slate-200 bg-white px-4 py-4 md:px-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase text-slate-400">Tenant</p>
            <h1 className="text-lg font-semibold text-slate-900">
              Operação #{tenantId}
            </h1>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="md:hidden"
            onClick={() => setIsOpen((prev) => !prev)}
            aria-expanded={isOpen}
            aria-label="Abrir menu"
          >
            {isOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-3 md:justify-end">
          {isLoading && <Badge variant="secondary">Carregando sessão...</Badge>}
          {isError && <Badge variant="danger">Sessão expirada</Badge>}
          {data && (
            <div className="text-left md:text-right">
              <p className="text-sm font-medium text-slate-900">{data.name}</p>
              <p className="text-xs text-slate-500">
                {data.email} · {data.role}
              </p>
            </div>
          )}
        </div>
      </div>
      {isOpen ? (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:hidden">
          <nav className="space-y-1">
            {sidebarItems.map((item) => (
              <Link
                key={item.href}
                href={`/t/${tenantId}/${item.href}`}
                className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
                onClick={() => setIsOpen(false)}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            ))}
          </nav>
          <Button
            variant="outline"
            className="mt-4 w-full"
            onClick={handleLogout}
          >
            Sair
          </Button>
        </div>
      ) : null}
    </header>
  );
}
