"use client";

import { FormEvent, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError, api } from "@/lib/api";
import { authApi } from "@/lib/auth";

interface DeliveryUser {
  id: number;
  tenant_id: number;
  email: string;
  name: string;
  role: string;
  active: boolean;
}

interface StatusMessage {
  type: "success" | "error";
  message: string;
}

const DELIVERY_ROLE = "DELIVERY";

export default function AdminDeliveryUsersPage() {
  const params = useParams<{ tenant_id: string }>();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<StatusMessage | null>(null);
  const [form, setForm] = useState({ name: "", email: "", password: "" });

  const tenantId = useMemo(() => {
    const parsed = Number(params.tenant_id);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [params.tenant_id]);

  const { data: currentUser, isLoading: meLoading } = useQuery({
    queryKey: ["admin-auth-me"],
    queryFn: () => authApi.me(),
  });

  const tenantMismatch =
    tenantId !== null &&
    currentUser?.tenant_id !== undefined &&
    Number(currentUser.tenant_id) !== Number(tenantId);

  const {
    data: deliveryUsers,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["delivery-users", tenantId],
    enabled: tenantId !== null && !tenantMismatch,
    queryFn: async () => {
      const users = await api.get<DeliveryUser[]>(`/api/admin/users?tenant_id=${tenantId}`);
      return users.filter((user) => user.role?.toUpperCase() === DELIVERY_ROLE);
    },
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post<DeliveryUser>(`/api/admin/${tenantId}/delivery-users`, {
        name: form.name,
        email: form.email,
        password: form.password,
      }),
    onSuccess: () => {
      setForm({ name: "", email: "", password: "" });
      setStatus({ type: "success", message: "Usuário de delivery criado com sucesso." });
      queryClient.invalidateQueries({ queryKey: ["delivery-users", tenantId] });
    },
    onError: (mutationError) => {
      const message =
        mutationError instanceof ApiError
          ? mutationError.message
          : "Não foi possível criar o usuário de delivery.";
      setStatus({ type: "error", message });
    },
  });

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatus(null);

    if (tenantId === null) {
      setStatus({ type: "error", message: "Tenant inválido na URL." });
      return;
    }

    if (tenantMismatch) {
      setStatus({ type: "error", message: "Você não tem acesso ao tenant informado." });
      return;
    }

    createMutation.mutate();
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Gestão de entregadores</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-slate-600">Tenant selecionado: {params.tenant_id}</p>

          {status ? (
            <p className={status.type === "success" ? "text-sm text-emerald-600" : "text-sm text-red-600"}>
              {status.message}
            </p>
          ) : null}

          {tenantId === null ? <p className="text-sm text-red-600">Tenant inválido.</p> : null}
          {tenantMismatch ? (
            <p className="text-sm text-red-600">Tenant não autorizado para o usuário autenticado.</p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Novo usuário de delivery</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 md:grid-cols-3" onSubmit={handleSubmit}>
            <Input
              placeholder="Nome"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              required
            />
            <Input
              placeholder="Email"
              type="email"
              value={form.email}
              onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              required
            />
            <Input
              placeholder="Senha"
              type="password"
              value={form.password}
              onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
              minLength={6}
              required
            />
            <div className="md:col-span-3">
              <Button type="submit" disabled={createMutation.isPending || meLoading || tenantId === null || tenantMismatch}>
                {createMutation.isPending ? "Criando..." : "Criar usuário de delivery"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Usuários de delivery</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? <p className="text-sm text-slate-500">Carregando usuários...</p> : null}
          {isError ? (
            <p className="text-sm text-red-600">
              {error instanceof ApiError ? error.message : "Erro ao carregar usuários de delivery."}
            </p>
          ) : null}

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Nome</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {deliveryUsers?.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>{user.id}</TableCell>
                  <TableCell>{user.name}</TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>{user.active ? "Ativo" : "Inativo"}</TableCell>
                </TableRow>
              ))}
              {!isLoading && (deliveryUsers?.length ?? 0) === 0 ? (
                <TableRow>
                  <TableCell className="text-sm text-slate-500" colSpan={4}>
                    Nenhum usuário de delivery cadastrado para este tenant.
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
