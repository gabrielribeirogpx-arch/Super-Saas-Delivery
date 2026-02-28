"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

interface CustomerOrder {
  id: number;
  status: string;
  total_cents: number;
  created_at: string;
}

interface CustomerDetail {
  id: number;
  name: string;
  phone: string;
  address: string | null;
  is_vip?: boolean;
  recurrence_segment?: string | null;
  total_orders: number;
  total_spent: number;
  orders: CustomerOrder[];
}

const RECURRENCE_COLORS: Record<string, string> = {
  novo: "bg-sky-50 text-sky-700 border-sky-200",
  frequente: "bg-emerald-50 text-emerald-700 border-emerald-200",
  recorrente: "bg-violet-50 text-violet-700 border-violet-200",
  ocasional: "bg-amber-50 text-amber-700 border-amber-200",
};

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const customerId = Number(params.id);

  const detailQuery = useQuery({
    queryKey: ["admin-customer-detail", customerId],
    enabled: Number.isFinite(customerId),
    queryFn: () => api.get<CustomerDetail>(`/api/admin/customers/${customerId}`),
  });

  if (detailQuery.isLoading) {
    return <p className="text-sm text-slate-500">Carregando cliente...</p>;
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
        Não foi possível carregar os detalhes do cliente.
      </div>
    );
  }

  const customer = detailQuery.data;
  const initial = customer.name?.trim()?.charAt(0)?.toUpperCase() || "C";
  const averageTicket = customer.total_orders > 0 ? customer.total_spent / customer.total_orders : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Detalhes do cliente</h1>
        <Button variant="outline" asChild>
          <Link href="/customers">Voltar</Link>
        </Button>
      </div>

      <Card className="border-slate-200/90 bg-gradient-to-b from-white to-slate-50/80">
        <CardContent className="space-y-6 p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-900 text-lg font-semibold text-white">
                {initial}
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-semibold text-slate-900">{customer.name}</h2>
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
                <p className="text-sm text-slate-600">{customer.phone}</p>
              </div>
            </div>
            <p className="text-sm text-slate-600">{customer.address || "Endereço não informado"}</p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Total de pedidos</p>
              <p className="text-2xl font-semibold text-slate-900">{customer.total_orders}</p>
            </div>
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
              <p className="text-xs uppercase tracking-wide text-emerald-700">Total gasto</p>
              <p className="text-2xl font-semibold text-emerald-900">R$ {(customer.total_spent / 100).toFixed(2)}</p>
            </div>
            <div className="rounded-xl border border-indigo-200 bg-indigo-50/60 p-4">
              <p className="text-xs uppercase tracking-wide text-indigo-700">Ticket médio</p>
              <p className="text-2xl font-semibold text-indigo-900">R$ {(averageTicket / 100).toFixed(2)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Timeline de pedidos</CardTitle>
        </CardHeader>
        <CardContent>
          {customer.orders.length === 0 ? (
            <p className="text-sm text-slate-500">Cliente sem pedidos.</p>
          ) : (
            <ol className="space-y-4">
              {customer.orders.map((order) => (
                <li key={order.id} className="relative rounded-xl border border-slate-200 bg-white p-4 pl-10">
                  <span className="absolute left-4 top-5 h-2.5 w-2.5 rounded-full bg-indigo-500" />
                  <div className="absolute bottom-0 left-[20px] top-8 w-px bg-slate-200" />
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium text-slate-900">Pedido #{order.id}</p>
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-600">
                      {order.status}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-slate-600">{new Date(order.created_at).toLocaleString("pt-BR")}</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">R$ {(order.total_cents / 100).toFixed(2)}</p>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
