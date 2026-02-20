"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { authApi } from "@/lib/auth";
import { sidebarItems } from "@/components/sidebar";
import { UserIdentity } from "@/components/UserIdentity";
import { useSession } from "@/hooks/use-session";
import { api } from "@/lib/api";

export function Topbar() {
  const { data, isLoading, isError } = useSession();
  const { data: tenant } = useQuery({
    queryKey: ["tenant", "header"],
    queryFn: () => api.get<{ business_name?: string; name?: string }>("/api/admin/tenant"),
    retry: false,
  });
  const [isOpen, setIsOpen] = useState(false);
  const router = useRouter();
  const storeName = tenant?.business_name ?? tenant?.name ?? "Minha Loja";

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } finally {
      router.push("/login");
    }
  };

  return (
    <header className="relative mt-8 bg-transparent px-4 md:px-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">{storeName}</h1>
            <p className="text-sm text-slate-500">Dashboard</p>
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
          {data && <UserIdentity user={data} onLogout={handleLogout} />}
        </div>
      </div>
      {isOpen ? (
        <div className="mt-4 rounded-xl border border-black/[0.06] bg-white p-4 shadow-[0_1px_2px_rgba(0,0,0,0.05)] md:hidden">
          <nav className="space-y-1">
            {sidebarItems.map((item) => {
              if (item.children) {
                return (
                  <div key={item.label} className="space-y-1">
                    <p className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-700">
                      <item.icon className="h-4 w-4" />
                      {item.label}
                    </p>
                    <div className="ml-7 space-y-1 border-l border-slate-200 pl-3">
                      {item.children.map((child) => (
                        <Link
                          key={child.href}
                          href={child.href}
                          className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-gray-100 transition-colors duration-150"
                          onClick={() => setIsOpen(false)}
                        >
                          {child.icon ? <child.icon className="h-4 w-4" /> : null}
                          {child.label}
                        </Link>
                      ))}
                    </div>
                  </div>
                );
              }

              return (
                <Link
                  key={item.href}
                  href={item.href ?? "#"}
                  className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-gray-100 transition-colors duration-150"
                  onClick={() => setIsOpen(false)}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <Button variant="outline" className="mt-4 w-full" onClick={handleLogout}>
            Sair
          </Button>
        </div>
      ) : null}
    </header>
  );
}
