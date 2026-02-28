"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";

interface CustomerItem {
  id: number;
  name: string;
  phone: string;
  is_vip?: boolean;
  recurrence_segment?: string | null;
  total_orders: number;
  total_spent: number;
  last_order_date: string | null;
}

interface CustomersResponse {
  items: CustomerItem[];
  total: number;
  page: number;
}

const PAGE_SIZE = 20;
const QUICK_FILTERS = ["all", "vip", "frequentes", "inativos"] as const;

type QuickFilter = (typeof QUICK_FILTERS)[number];

const RECURRENCE_COLORS: Record<string, string> = {
  novo: "bg-sky-50 text-sky-700 border-sky-200",
  frequente: "bg-emerald-50 text-emerald-700 border-emerald-200",
  recorrente: "bg-violet-50 text-violet-700 border-violet-200",
  ocasional: "bg-amber-50 text-amber-700 border-amber-200",
};

function isInactive(lastOrderDate: string | null) {
  if (!lastOrderDate) {
    return true;
  }
  const sixtyDaysMs = 1000 * 60 * 60 * 24 * 60;
  return Date.now() - new Date(lastOrderDate).getTime() > sixtyDaysMs;
}

function isFrequent(customer: CustomerItem) {
  const segment = customer.recurrence_segment?.toLowerCase() ?? "";
  return segment.includes("frequen") || segment.includes("recorren") || customer.total_orders >= 5;
}

export default function CustomersPage() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  const selectedFilter = useMemo<QuickFilter>(() => {
    const current = searchParams.get("filter");
    return QUICK_FILTERS.includes(current as QuickFilter) ? (current as QuickFilter) : "all";
  }, [searchParams]);

  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const customersQuery = useQuery({
    queryKey: ["admin-customers", page, searchTerm],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        limit: String(PAGE_SIZE),
      });
      if (searchTerm) {
        params.set("search", searchTerm);
      }
      return api.get<CustomersResponse>(`/api/admin/customers?${params.toString()}`);
    },
  });

  const totalPages = useMemo(() => {
    const total = customersQuery.data?.total ?? 0;
    return Math.max(1, Math.ceil(total / PAGE_SIZE));
  }, [customersQuery.data?.total]);

  const filteredCustomers = useMemo(() => {
    const items = customersQuery.data?.items ?? [];
    switch (selectedFilter) {
      case "vip":
        return items.filter((customer) => customer.is_vip);
      case "frequentes":
        return items.filter(isFrequent);
      case "inativos":
        return items.filter((customer) => isInactive(customer.last_order_date));
      default:
        return items;
    }
  }, [customersQuery.data?.items, selectedFilter]);

  const summary = useMemo(() => {
    const items = customersQuery.data?.items ?? [];
    const vipCount = items.filter((customer) => customer.is_vip).length;
    const inactiveCount = items.filter((customer) => isInactive(customer.last_order_date)).length;
    const totalOrders = items.reduce((acc, customer) => acc + customer.total_orders, 0);
    const totalSpent = items.reduce((acc, customer) => acc + customer.total_spent, 0);
    return {
      total: customersQuery.data?.total ?? 0,
      vipCount,
      inactiveCount,
      averageTicket: totalOrders > 0 ? totalSpent / totalOrders : 0,
    };
  }, [customersQuery.data]);

  const setFilter = (filter: QuickFilter) => {
    const params = new URLSearchParams(searchParams.toString());
    if (filter === "all") {
      params.delete("filter");
    } else {
      params.set("filter", filter);
    }
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  };

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPage(1);
    setSearchTerm(searchInput.trim());
  };

  return (
    <Card className="border-slate-200/80 bg-gradient-to-b from-white to-slate-50/60 shadow-sm">
      <CardHeader className="space-y-4">
        <CardTitle>Clientes</CardTitle>
        <form onSubmit={handleSearch} className="flex flex-col gap-2 sm:flex-row">
          <Input
            placeholder="Buscar por nome ou telefone"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
          <Button type="submit">Buscar</Button>
        </form>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Total Clientes</p>
            <p className="text-2xl font-semibold text-slate-900">{summary.total}</p>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
            <p className="text-xs uppercase tracking-wide text-amber-700">Total VIP</p>
            <p className="text-2xl font-semibold text-amber-900">{summary.vipCount}</p>
          </div>
          <div className="rounded-xl border border-rose-200 bg-rose-50/70 p-4">
            <p className="text-xs uppercase tracking-wide text-rose-700">Total Inativos</p>
            <p className="text-2xl font-semibold text-rose-900">{summary.inactiveCount}</p>
          </div>
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4">
            <p className="text-xs uppercase tracking-wide text-emerald-700">Ticket Médio Geral</p>
            <p className="text-2xl font-semibold text-emerald-900">R$ {(summary.averageTicket / 100).toFixed(2)}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {QUICK_FILTERS.map((filter) => {
            const isActive = selectedFilter === filter;
            return (
              <Button
                key={filter}
                type="button"
                size="sm"
                variant={isActive ? "default" : "outline"}
                className="capitalize"
                onClick={() => setFilter(filter)}
              >
                {filter === "all" ? "Todos" : filter}
              </Button>
            );
          })}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {customersQuery.isLoading && <p className="text-sm text-slate-500">Carregando clientes...</p>}

        {customersQuery.isError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
            Não foi possível carregar os clientes.
          </div>
        )}

        {customersQuery.data && (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nome</TableHead>
                  <TableHead>Telefone</TableHead>
                  <TableHead>Total de pedidos</TableHead>
                  <TableHead>Total gasto</TableHead>
                  <TableHead>Último pedido</TableHead>
                  <TableHead className="text-right">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCustomers.map((customer) => (
                  <TableRow key={customer.id}>
                    <TableCell>
                      <div className="space-y-1">
                        <p className="font-medium text-slate-900">{customer.name}</p>
                        <div className="flex flex-wrap items-center gap-1">
                          {customer.is_vip && (
                            <span className="rounded-full border border-amber-300 bg-amber-100 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-amber-800">
                              VIP
                            </span>
                          )}
                          {customer.recurrence_segment && (
                            <span
                              className={`rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize ${
                                RECURRENCE_COLORS[customer.recurrence_segment.toLowerCase()] ??
                                "border-indigo-200 bg-indigo-50 text-indigo-700"
                              }`}
                            >
                              {customer.recurrence_segment}
                            </span>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>{customer.phone}</TableCell>
                    <TableCell>{customer.total_orders}</TableCell>
                    <TableCell>R$ {(customer.total_spent / 100).toFixed(2)}</TableCell>
                    <TableCell>
                      {customer.last_order_date
                        ? new Date(customer.last_order_date).toLocaleString("pt-BR")
                        : "-"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="outline">
                        <Link href={`/customers/${customer.id}`}>Ver histórico</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {filteredCustomers.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-sm text-slate-500">
                      Nenhum cliente encontrado.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>

            <div className="flex items-center justify-between gap-2">
              <p className="text-xs text-slate-500">
                Página {customersQuery.data.page} de {totalPages} · {customersQuery.data.total} clientes
              </p>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((previous) => Math.max(1, previous - 1))}
                >
                  Anterior
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((previous) => previous + 1)}
                >
                  Próxima
                </Button>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
