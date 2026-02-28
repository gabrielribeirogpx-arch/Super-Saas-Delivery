"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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
  total_orders: number;
  total_spent: number;
  orders: CustomerOrder[];
}

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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Detalhes do cliente</h1>
        <Button variant="outline" asChild>
          <Link href="/customers">Voltar</Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Informações básicas</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm text-slate-700 md:grid-cols-2">
          <p><span className="font-medium">Nome:</span> {customer.name}</p>
          <p><span className="font-medium">Telefone:</span> {customer.phone}</p>
          <p className="md:col-span-2"><span className="font-medium">Endereço:</span> {customer.address || "-"}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Estatísticas</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-slate-200 p-4">
            <p className="text-xs text-slate-500">Total de pedidos</p>
            <p className="text-2xl font-semibold text-slate-900">{customer.total_orders}</p>
          </div>
          <div className="rounded-lg border border-slate-200 p-4">
            <p className="text-xs text-slate-500">Total gasto</p>
            <p className="text-2xl font-semibold text-slate-900">R$ {(customer.total_spent / 100).toFixed(2)}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Lista de pedidos</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Pedido</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Total</TableHead>
                <TableHead>Data</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {customer.orders.map((order) => (
                <TableRow key={order.id}>
                  <TableCell>#{order.id}</TableCell>
                  <TableCell>{order.status}</TableCell>
                  <TableCell>R$ {(order.total_cents / 100).toFixed(2)}</TableCell>
                  <TableCell>{new Date(order.created_at).toLocaleString("pt-BR")}</TableCell>
                </TableRow>
              ))}
              {customer.orders.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-sm text-slate-500">
                    Cliente sem pedidos.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
