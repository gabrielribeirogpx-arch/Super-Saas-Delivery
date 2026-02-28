"use client";

import Link from "next/link";
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

export default function CustomersPage() {
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

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPage(1);
    setSearchTerm(searchInput.trim());
  };

  return (
    <Card>
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
                {customersQuery.data.items.map((customer) => (
                  <TableRow key={customer.id}>
                    <TableCell>{customer.name}</TableCell>
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
                {customersQuery.data.items.length === 0 && (
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
