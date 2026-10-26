"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";

interface InventoryItem {
  id: number;
  name: string;
  unit: string;
  current_stock: number;
  min_stock_level: number;
  cost_cents: number;
}

interface InventoryMovement {
  id: number;
  item_name: string;
  type: string;
  quantity: number;
  reason?: string;
  created_at: string;
}

function formatDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

export default function InventoryPage() {
  const [fromDate, setFromDate] = useState(formatDate(new Date(Date.now() - 6 * 24 * 60 * 60 * 1000)));
  const [toDate, setToDate] = useState(formatDate(new Date()));

  const { data, isLoading, isError } = useQuery({
    queryKey: ["inventory", fromDate, toDate],
    queryFn: async () => {
      const [items, movements] = await Promise.all([
        api.get<InventoryItem[]>(`/api/inventory/items`),
        api.get<InventoryMovement[]>(
          `/api/inventory/movements?de=${fromDate}&para=${toDate}`
        ),
      ]);
      return { items, movements };
    },
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Estoque atual</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <p className="text-sm text-slate-500">Carregando estoque...</p>}
          {isError && (
            <p className="text-sm text-red-600">Erro ao carregar estoque.</p>
          )}
          <Table mobileCards>
            <TableHeader>
              <TableRow>
                <TableHead>Item</TableHead>
                <TableHead>Unidade</TableHead>
                <TableHead>Atual</TableHead>
                <TableHead>Mínimo</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((item) => {
                const low = item.current_stock <= item.min_stock_level;
                return (
                  <TableRow key={item.id}>
                    <TableCell mobileLabel="Item">{item.name}</TableCell>
                    <TableCell mobileLabel="Unidade">{item.unit}</TableCell>
                    <TableCell mobileLabel="Atual">{item.current_stock}</TableCell>
                    <TableCell mobileLabel="Mínimo">{item.min_stock_level}</TableCell>
                    <TableCell mobileLabel="Status">
                      <Badge variant={low ? "danger" : "success"}>
                        {low ? "Baixo" : "OK"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Movimentações</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <div>
              <label className="text-xs text-slate-500">De</label>
              <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-slate-500">Até</label>
              <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
            </div>
          </div>
          <Table mobileCards>
            <TableHeader>
              <TableRow>
                <TableHead>Item</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Quantidade</TableHead>
                <TableHead>Motivo</TableHead>
                <TableHead>Data</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.movements.map((movement) => (
                <TableRow key={movement.id}>
                  <TableCell mobileLabel="Item">{movement.item_name}</TableCell>
                  <TableCell mobileLabel="Tipo">{movement.type}</TableCell>
                  <TableCell mobileLabel="Quantidade">{movement.quantity}</TableCell>
                  <TableCell mobileLabel="Motivo">{movement.reason ?? "-"}</TableCell>
                  <TableCell mobileLabel="Data">
                    {new Date(movement.created_at).toLocaleString("pt-BR")}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
