"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useSession } from "@/hooks/use-session";
import { api } from "@/lib/api";

interface WhatsAppConfig {
  id: number;
  tenant_id: number;
  provider: string;
  phone_number_id?: string | null;
  waba_id?: string | null;
  access_token_masked?: string | null;
  verify_token?: string | null;
  webhook_secret?: string | null;
  is_enabled: boolean;
}

interface WhatsAppLog {
  id: number;
  direction: string;
  to_phone?: string | null;
  from_phone?: string | null;
  status: string;
  created_at: string;
}

export default function WhatsAppPage() {
  const queryClient = useQueryClient();
  const { data: session, isLoading: isSessionLoading } = useSession();
  const [testPhone, setTestPhone] = useState("");
  const [testMessage, setTestMessage] = useState("Olá! Teste de mensagem.");
  const tenantId = session?.tenant_id;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["whatsapp", tenantId],
    queryFn: () => api.get<WhatsAppConfig>(`/api/admin/${tenantId}/whatsapp/config`),
    enabled: Boolean(tenantId),
  });

  const { data: logs } = useQuery({
    queryKey: ["whatsapp-logs", tenantId],
    queryFn: () => api.get<WhatsAppLog[]>(`/api/admin/${tenantId}/whatsapp/logs?limit=20`),
    enabled: Boolean(tenantId),
  });

  const updateMutation = useMutation({
    mutationFn: (payload: Partial<WhatsAppConfig> & { access_token?: string; update_token?: boolean }) =>
      api.put<WhatsAppConfig>(`/api/admin/${tenantId}/whatsapp/config`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["whatsapp", tenantId] }),
  });

  const testMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/admin/${tenantId}/whatsapp/test-message`, {
        phone: testPhone,
        message: testMessage,
      }),
  });

  if (isSessionLoading || isLoading) {
    return <p className="text-sm text-slate-500">Carregando configuração...</p>;
  }

  if (!tenantId || isError || !data) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
        Não foi possível carregar configurações.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Configuração WhatsApp</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="text-xs text-slate-500">Provider</label>
              <Select
                value={data.provider}
                onChange={(e) => updateMutation.mutate({
                  provider: e.target.value,
                  phone_number_id: data.phone_number_id,
                  waba_id: data.waba_id,
                  verify_token: data.verify_token,
                  webhook_secret: data.webhook_secret,
                  is_enabled: data.is_enabled,
                })}
              >
                <option value="mock">mock</option>
                <option value="cloud">cloud</option>
              </Select>
            </div>
            <div>
              <label className="text-xs text-slate-500">Phone ID</label>
              <Input
                value={data.phone_number_id ?? ""}
                onChange={(e) =>
                  updateMutation.mutate({
                    provider: data.provider,
                    phone_number_id: e.target.value,
                    waba_id: data.waba_id,
                    verify_token: data.verify_token,
                    webhook_secret: data.webhook_secret,
                    is_enabled: data.is_enabled,
                  })
                }
              />
            </div>
            <div>
              <label className="text-xs text-slate-500">WABA ID</label>
              <Input
                value={data.waba_id ?? ""}
                onChange={(e) =>
                  updateMutation.mutate({
                    provider: data.provider,
                    phone_number_id: data.phone_number_id,
                    waba_id: e.target.value,
                    verify_token: data.verify_token,
                    webhook_secret: data.webhook_secret,
                    is_enabled: data.is_enabled,
                  })
                }
              />
            </div>
            <div>
              <label className="text-xs text-slate-500">Verify token</label>
              <Input
                value={data.verify_token ?? ""}
                onChange={(e) =>
                  updateMutation.mutate({
                    provider: data.provider,
                    phone_number_id: data.phone_number_id,
                    waba_id: data.waba_id,
                    verify_token: e.target.value,
                    webhook_secret: data.webhook_secret,
                    is_enabled: data.is_enabled,
                  })
                }
              />
            </div>
            <div>
              <label className="text-xs text-slate-500">Webhook secret</label>
              <Input
                value={data.webhook_secret ?? ""}
                onChange={(e) =>
                  updateMutation.mutate({
                    provider: data.provider,
                    phone_number_id: data.phone_number_id,
                    waba_id: data.waba_id,
                    verify_token: data.verify_token,
                    webhook_secret: e.target.value,
                    is_enabled: data.is_enabled,
                  })
                }
              />
            </div>
            <div>
              <label className="text-xs text-slate-500">Token (mascarado)</label>
              <Input value={data.access_token_masked ?? ""} disabled />
            </div>
            <div className="flex items-end gap-2">
              <Button
                variant={data.is_enabled ? "default" : "outline"}
                onClick={() =>
                  updateMutation.mutate({
                    provider: data.provider,
                    phone_number_id: data.phone_number_id,
                    waba_id: data.waba_id,
                    verify_token: data.verify_token,
                    webhook_secret: data.webhook_secret,
                    is_enabled: !data.is_enabled,
                  })
                }
              >
                {data.is_enabled ? "Desativar" : "Ativar"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Teste de envio</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            placeholder="Telefone com DDI"
            value={testPhone}
            onChange={(e) => setTestPhone(e.target.value)}
          />
          <Input
            placeholder="Mensagem"
            value={testMessage}
            onChange={(e) => setTestMessage(e.target.value)}
          />
          <Button onClick={() => testMutation.mutate()}>
            {testMutation.isPending ? "Enviando..." : "Enviar teste"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0 gap-3">
          <CardTitle>Logs recentes</CardTitle>
          <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
            {logs?.length ?? 0} {(logs?.length ?? 0) === 1 ? "registro" : "registros"}
          </span>
        </CardHeader>
        <CardContent className="px-3 pb-3 sm:px-6 sm:pb-6">
          <Table
            className="table-fixed"
            containerClassName="max-h-[440px] overflow-x-hidden overflow-y-auto rounded-lg border border-slate-200"
          >
            <TableHeader className="sticky top-0 z-10 bg-slate-50 shadow-[0_1px_0_rgb(226,232,240)]">
              <TableRow>
                <TableHead className="w-[12%] px-2 sm:px-4">ID</TableHead>
                <TableHead className="w-[18%] px-2 sm:px-4">Direção</TableHead>
                <TableHead className="w-[25%] px-2 sm:px-4">Destino</TableHead>
                <TableHead className="w-[18%] px-2 sm:px-4">Status</TableHead>
                <TableHead className="w-[27%] px-2 sm:px-4">Data</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs?.map((log) => (
                <TableRow key={log.id}>
                  <TableCell className="break-words px-2 sm:px-4">#{log.id}</TableCell>
                  <TableCell className="break-words px-2 sm:px-4">{log.direction}</TableCell>
                  <TableCell className="break-words px-2 sm:px-4">{log.to_phone ?? log.from_phone ?? "-"}</TableCell>
                  <TableCell className="break-words px-2 sm:px-4">{log.status}</TableCell>
                  <TableCell className="break-words px-2 sm:px-4">
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
