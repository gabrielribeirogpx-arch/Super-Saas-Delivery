"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";

interface AuditLog {
  id: number;
  user_name?: string | null;
  user_email?: string | null;
  action: string;
  entity_type?: string | null;
  entity_id?: number | null;
  created_at: string;
}

export default function AuditPage() {
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["audit", fromDate, toDate],
    queryFn: () => {
      const query = new URLSearchParams();
      if (fromDate) query.set("from", fromDate);
      if (toDate) query.set("to", toDate);
      return api.get<AuditLog[]>(`/api/admin/audit?${query.toString()}`);
    },
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Auditoria</CardTitle>
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

          {isLoading && <p className="text-sm text-slate-500">Carregando...</p>}
          {isError && (
            <p className="text-sm text-red-600">Erro ao carregar auditoria.</p>
          )}

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Usuário</TableHead>
                <TableHead>Ação</TableHead>
                <TableHead>Entidade</TableHead>
                <TableHead>Data</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.map((log) => (
                <TableRow key={log.id}>
                  <TableCell>#{log.id}</TableCell>
                  <TableCell>
                    {log.user_name ?? "-"}
                    <div className="text-xs text-slate-500">{log.user_email}</div>
                  </TableCell>
                  <TableCell>{log.action}</TableCell>
                  <TableCell>
                    {log.entity_type ?? "-"} {log.entity_id ? `#${log.entity_id}` : ""}
                  </TableCell>
                  <TableCell>
                    {new Date(log.created_at).toLocaleString("pt-BR")}
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
