"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";
import { ChevronRight, Phone, Search, UsersRound } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LoadingExperience } from "@/components/ui/loading-experience";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";

interface CustomerItem {
  id: number;
  name: string | null;
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

const RECURRENCE_LABELS: Record<string, string> = {
  frequent: "Frequente", frequente: "Frequente", regular: "Recorrente", recorrente: "Recorrente",
  occasional: "Ocasional", ocasional: "Ocasional", inactive: "Inativo", inativo: "Inativo", novo: "Novo",
};
const currency = (cents: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(cents / 100);
function phoneLabel(phone: string | null | undefined) {
  const digits = (phone ?? "").replace(/\D/g, "");
  const local = digits.length === 13 && digits.startsWith("55") ? digits.slice(2) : digits;
  if (local.length === 11) return `(${local.slice(0, 2)}) ${local.slice(2, 7)}-${local.slice(7)}`;
  if (local.length === 10) return `(${local.slice(0, 2)}) ${local.slice(2, 6)}-${local.slice(6)}`;
  return phone || "Telefone não informado";
}

const RECURRENCE_COLORS: Record<string, string> = {
  frequent: "bg-emerald-50 text-emerald-700 border-emerald-200",
  regular: "bg-violet-50 text-violet-700 border-violet-200",
  occasional: "bg-slate-50 text-slate-700 border-slate-200",
  inactive: "bg-slate-100 text-slate-600 border-slate-200",
  novo: "bg-slate-50 text-slate-800 border-slate-200",
  frequente: "bg-emerald-50 text-emerald-700 border-emerald-200",
  recorrente: "bg-violet-50 text-violet-700 border-violet-200",
  ocasional: "bg-slate-50 text-slate-700 border-slate-200",
};

function CustomerBadges({ customer }: { customer: CustomerItem }) {
  const segment = customer.recurrence_segment?.toLowerCase();
  return <div className="flex flex-wrap items-center gap-1.5">
    {customer.is_vip && <span className="whitespace-nowrap rounded-full border border-brand-200 bg-brand-50 px-2.5 py-1 text-[10px] font-semibold text-brand-700">VIP</span>}
    {segment && <span className={`whitespace-nowrap rounded-full border px-2.5 py-1 text-[10px] font-medium ${RECURRENCE_COLORS[segment] ?? "border-slate-200 bg-slate-50 text-slate-600"}`}>{RECURRENCE_LABELS[segment] ?? customer.recurrence_segment}</span>}
  </div>;
}

function CustomerMobileCard({ customer }: { customer: CustomerItem }) {
  return <article aria-label={`Cliente ${customer.name || "sem nome"}`} className="min-w-0 rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
    <div className="flex items-start gap-3"><span aria-hidden="true" className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-50 text-base font-bold text-brand-700">{customer.name?.trim().charAt(0).toUpperCase() || "C"}</span><div className="min-w-0 flex-1"><h2 className="break-words text-sm font-semibold leading-5 text-slate-950">{customer.name || "Cliente"}</h2><p className="mt-1 flex items-center gap-1.5 text-xs text-slate-500"><Phone aria-hidden="true" className="h-3 w-3 shrink-0" /><span className="min-w-0 break-words">{phoneLabel(customer.phone)}</span></p></div></div>
    <div className="mt-3"><CustomerBadges customer={customer} /></div>
    <div className="mt-3 grid grid-cols-2 gap-2 rounded-xl bg-slate-50 p-3"><div><p className="text-[11px] text-slate-500">Pedidos</p><p className="mt-1 text-lg font-bold text-slate-900">{customer.total_orders}</p></div><div className="min-w-0"><p className="text-[11px] text-slate-500">Total gasto</p><p className="mt-1 break-words text-lg font-bold text-slate-900">{currency(customer.total_spent)}</p></div></div>
    <div className="mt-3 flex items-center justify-between gap-2"><div className="min-w-0"><p className="text-[10px] text-slate-400">Último pedido</p><p className="mt-0.5 text-xs font-medium text-slate-600">{customer.last_order_date ? new Date(customer.last_order_date).toLocaleDateString("pt-BR") : "Sem pedidos"}</p></div><Link href={`/customers/${customer.id}`} className="inline-flex min-h-11 shrink-0 items-center gap-1 rounded-xl bg-brand-50 px-3 text-xs font-semibold text-brand-700">Ver histórico<ChevronRight aria-hidden="true" className="h-4 w-4" /></Link></div>
  </article>;
}

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
    <Card className="min-w-0 border-0 bg-transparent shadow-none lg:border lg:border-slate-200/80 lg:bg-white lg:shadow-sm">
      <CardHeader className="space-y-4 p-0 pb-4 lg:p-6">
        <div><h1 className="text-2xl font-bold tracking-tight text-slate-950">Clientes</h1><p className="mt-1 text-sm text-slate-500">Conheça quem compra na sua loja.</p></div>
        <form onSubmit={handleSearch} className="flex min-w-0 gap-2">
          <Input aria-label="Buscar clientes por nome ou telefone" className="min-w-0 flex-1 rounded-xl"
            placeholder="Nome ou telefone"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
          <Button type="submit" aria-label="Buscar clientes" className="shrink-0 gap-2 rounded-xl"><Search aria-hidden="true" className="h-4 w-4" /><span className="hidden sm:inline">Buscar</span></Button>
        </form>

        <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4 lg:gap-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-[11px] font-medium leading-4 text-slate-500">Clientes encontrados</p>
            <p className="mt-1 break-words text-xl font-semibold text-slate-900">{summary.total}</p>
          </div>
          <div className="rounded-xl border border-brand-200 bg-brand-50/70 p-4">
            <p className="text-[11px] font-medium leading-4 text-brand-700">VIP nesta página</p>
            <p className="mt-1 break-words text-xl font-semibold text-brand-900">{summary.vipCount}</p>
          </div>
          <div className="rounded-xl border border-rose-200 bg-rose-50/70 p-4">
            <p className="text-[11px] font-medium leading-4 text-rose-700">Inativos nesta página</p>
            <p className="mt-1 break-words text-xl font-semibold text-rose-900">{summary.inactiveCount}</p>
          </div>
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4">
            <p className="text-[11px] font-medium leading-4 text-emerald-700">Ticket médio da página</p>
            <p className="mt-1 break-words text-xl font-semibold text-emerald-900">{currency(summary.averageTicket)}</p>
          </div>
        </div>

        <nav aria-label="Filtrar clientes" className="grid grid-cols-4 gap-1 rounded-2xl border border-slate-200 bg-white p-1 lg:flex lg:flex-wrap lg:gap-2 lg:border-0 lg:p-0">
          {QUICK_FILTERS.map((filter) => {
            const isActive = selectedFilter === filter;
            return (
              <Button
                key={filter}
                type="button"
                size="sm"
                variant={isActive ? "default" : "outline"}
                aria-pressed={isActive}
                className="min-w-0 rounded-xl px-1 text-[11px] sm:px-3 sm:text-sm"
                onClick={() => setFilter(filter)}
              >
                {({ all: "Todos", vip: "VIP", frequentes: "Frequentes", inativos: "Inativos" })[filter]}
              </Button>
            );
          })}
        </nav>
        <p className="text-[11px] leading-4 text-slate-500">Filtros rápidos e indicadores de perfil consideram os clientes desta página.</p>
      </CardHeader>
      <CardContent className="min-w-0 space-y-4 p-0 lg:p-6 lg:pt-0">
        {customersQuery.isLoading && <LoadingExperience label="Buscando clientes" compact />}

        {customersQuery.isError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
            Não foi possível carregar os clientes.
          </div>
        )}

        {customersQuery.data && (
          <>
            <div className="space-y-3 lg:hidden">
              {filteredCustomers.map(customer => <CustomerMobileCard key={customer.id} customer={customer} />)}
              {filteredCustomers.length === 0 && <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-6 text-center"><UsersRound aria-hidden="true" className="mx-auto h-7 w-7 text-slate-300" /><p className="mt-2 text-sm font-semibold text-slate-700">Nenhum cliente encontrado.</p><p className="mt-1 text-xs leading-5 text-slate-500">Ajuste a busca ou os filtros para ver outros clientes.</p></div>}
            </div>
            <div className="hidden lg:block"><Table>
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
                        <CustomerBadges customer={customer} />
                      </div>
                    </TableCell>
                    <TableCell>{phoneLabel(customer.phone)}</TableCell>
                    <TableCell>{customer.total_orders}</TableCell>
                    <TableCell>{currency(customer.total_spent)}</TableCell>
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
            </Table></div>

            <nav aria-label="Paginação de clientes" className="flex flex-col items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-3 sm:flex-row">
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
            </nav>
          </>
        )}
      </CardContent>
    </Card>
  );
}
