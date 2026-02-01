"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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

export default function WhatsAppPage({ params }: { params: { slug: string } }) {
  const tenantId = params.slug;
  const queryClient = useQueryClient();
  const [testPhone, setTestPhone] = useState("");
  const [testMessage, setTestMessage] = useState("Olá! Teste de mensagem.");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["whatsapp", tenantId],
    queryFn: () => api.get<WhatsAppConfig>(`/api/admin/${tenantId}/whatsapp/config`),
  });

  const { data: logs } = useQuery({
    queryKey: ["whatsapp-logs", tenantId],
    queryFn: () => api.get<WhatsAppLog[]>(`/api/admin/${tenantId}/whatsapp/logs?limit=20`),
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

  if (isLoading) {
    return <p className="text-sm text-slate-500">Carregando configuração...</p>;
  }

  if (isError || !data) {
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
        <CardHeader>
          <CardTitle>Logs recentes</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Direção</TableHead>
                <TableHead>Destino</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Data</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs?.map((log) => (
                <TableRow key={log.id}>
                  <TableCell>#{log.id}</TableCell>
                  <TableCell>{log.direction}</TableCell>
                  <TableCell>{log.to_phone ?? log.from_phone ?? "-"}</TableCell>
                  <TableCell>{log.status}</TableCell>
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
