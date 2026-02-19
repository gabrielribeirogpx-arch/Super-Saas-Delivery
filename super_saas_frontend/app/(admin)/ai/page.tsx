"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useSession } from "@/hooks/use-session";
import { api } from "@/lib/api";

interface AIConfig {
  id: number;
  tenant_id: number;
  provider: string;
  enabled: boolean;
  model?: string | null;
  temperature?: number | null;
  system_prompt?: string | null;
}

interface AILog {
  id: number;
  phone?: string | null;
  direction: string;
  provider: string;
  error?: string | null;
  created_at: string;
}

export default function AiPage() {
  const queryClient = useQueryClient();
  const { data: session, isLoading: isSessionLoading } = useSession();
  const tenantId = session?.tenant_id;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["ai", tenantId],
    queryFn: () => api.get<AIConfig>(`/api/admin/${tenantId}/ai/config`),
    enabled: Boolean(tenantId),
  });

  const { data: logs } = useQuery({
    queryKey: ["ai-logs", tenantId],
    queryFn: () => api.get<AILog[]>(`/api/admin/${tenantId}/ai/logs?limit=20`),
    enabled: Boolean(tenantId),
  });

  const updateMutation = useMutation({
    mutationFn: (payload: AIConfig) => api.put(`/api/admin/${tenantId}/ai/config`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai", tenantId] }),
  });

  if (isSessionLoading || isLoading) {
    return <p className="text-sm text-slate-500">Carregando configuração...</p>;
  }

  if (!tenantId || isError || !data) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
        Não foi possível carregar IA.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Configuração IA</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="text-xs text-slate-500">Provider</label>
            <Select
              value={data.provider}
              onChange={(e) => updateMutation.mutate({ ...data, provider: e.target.value })}
            >
              <option value="mock">mock</option>
              <option value="gemini">gemini</option>
            </Select>
          </div>
          <div>
            <label className="text-xs text-slate-500">Model</label>
            <Input
              value={data.model ?? ""}
              onChange={(e) => updateMutation.mutate({ ...data, model: e.target.value })}
            />
          </div>
          <div>
            <label className="text-xs text-slate-500">Temperatura</label>
            <Input
              type="number"
              step="0.1"
              value={data.temperature ?? 0.2}
              onChange={(e) =>
                updateMutation.mutate({ ...data, temperature: Number(e.target.value) })
              }
            />
          </div>
          <div>
            <label className="text-xs text-slate-500">System prompt</label>
            <Input
              value={data.system_prompt ?? ""}
              onChange={(e) => updateMutation.mutate({ ...data, system_prompt: e.target.value })}
            />
          </div>
          <div className="flex items-end">
            <Button onClick={() => updateMutation.mutate({ ...data, enabled: !data.enabled })}>
              {data.enabled ? "Desativar" : "Ativar"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Logs IA</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Telefone</TableHead>
                <TableHead>Direção</TableHead>
                <TableHead>Provider</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs?.map((log) => (
                <TableRow key={log.id}>
                  <TableCell>#{log.id}</TableCell>
                  <TableCell>{log.phone ?? "-"}</TableCell>
                  <TableCell>{log.direction}</TableCell>
                  <TableCell>{log.provider}</TableCell>
                  <TableCell>{log.error ? "Erro" : "OK"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
