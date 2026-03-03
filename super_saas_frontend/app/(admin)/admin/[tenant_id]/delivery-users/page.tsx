"use client";

import { FormEvent, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError, api } from "@/lib/api";
import { authApi } from "@/lib/auth";

interface DeliveryUser {
  id: number;
  tenant_id: number;
  name: string;
  phone: string;
  active: boolean;
}

interface DeliveryUserFormState {
  name: string;
  phone: string;
  password: string;
  active: boolean;
}

interface StatusMessage {
  type: "success" | "error";
  message: string;
}

const INITIAL_FORM: DeliveryUserFormState = {
  name: "",
  phone: "",
  password: "",
  active: true,
};

export default function AdminDeliveryUsersManagementPage() {
  const params = useParams<{ tenant_id: string }>();
  const queryClient = useQueryClient();

  const [status, setStatus] = useState<StatusMessage | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<DeliveryUser | null>(null);
  const [form, setForm] = useState<DeliveryUserFormState>(INITIAL_FORM);

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

  const listQuery = useQuery({
    queryKey: ["admin-delivery-users", tenantId],
    enabled: tenantId !== null && !tenantMismatch,
    queryFn: () => api.get<DeliveryUser[]>(`/api/admin/${tenantId}/delivery-users`),
  });

  const createMutation = useMutation({
    mutationFn: (payload: DeliveryUserFormState) =>
      api.post<DeliveryUser>(`/api/admin/${tenantId}/delivery-users`, payload),
    onSuccess: () => {
      setStatus({ type: "success", message: "Entregador criado com sucesso." });
      closeModal();
      queryClient.invalidateQueries({ queryKey: ["admin-delivery-users", tenantId] });
    },
    onError: (cause) => {
      setStatus({
        type: "error",
        message: cause instanceof ApiError ? cause.message : "Não foi possível criar o entregador.",
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: (payload: DeliveryUserFormState & { id: number }) =>
      api.put<DeliveryUser>(`/api/admin/${tenantId}/delivery-users/${payload.id}`, {
        name: payload.name,
        phone: payload.phone,
        password: payload.password || undefined,
        active: payload.active,
      }),
    onSuccess: () => {
      setStatus({ type: "success", message: "Entregador atualizado com sucesso." });
      closeModal();
      queryClient.invalidateQueries({ queryKey: ["admin-delivery-users", tenantId] });
    },
    onError: (cause) => {
      setStatus({
        type: "error",
        message: cause instanceof ApiError ? cause.message : "Não foi possível atualizar o entregador.",
      });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (payload: { id: number; active: boolean }) =>
      api.patch<DeliveryUser>(`/api/admin/${tenantId}/delivery-users/${payload.id}`, { active: payload.active }),
    onSuccess: (_, variables) => {
      setStatus({
        type: "success",
        message: variables.active ? "Entregador ativado com sucesso." : "Entregador desativado com sucesso.",
      });
      queryClient.invalidateQueries({ queryKey: ["admin-delivery-users", tenantId] });
    },
    onError: (cause) => {
      setStatus({
        type: "error",
        message: cause instanceof ApiError ? cause.message : "Não foi possível alterar o status do entregador.",
      });
    },
  });

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingUser(null);
    setForm(INITIAL_FORM);
  };

  const openCreateModal = () => {
    setStatus(null);
    setEditingUser(null);
    setForm(INITIAL_FORM);
    setIsModalOpen(true);
  };

  const openEditModal = (user: DeliveryUser) => {
    setStatus(null);
    setEditingUser(user);
    setForm({
      name: user.name,
      phone: user.phone,
      password: "",
      active: user.active,
    });
    setIsModalOpen(true);
  };

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

    if (!editingUser && form.password.trim().length < 6) {
      setStatus({ type: "error", message: "Senha deve ter ao menos 6 caracteres." });
      return;
    }

    if (editingUser) {
      updateMutation.mutate({ ...form, id: editingUser.id });
      return;
    }

    createMutation.mutate(form);
  };

  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle>Gestão de entregadores</CardTitle>
            <Button onClick={openCreateModal} disabled={meLoading || tenantId === null || tenantMismatch}>
              <Plus className="mr-2 h-4 w-4" />
              Novo Entregador
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-slate-600">Tenant selecionado: {params.tenant_id}</p>

          {status ? (
            <p className={status.type === "success" ? "text-sm text-emerald-600" : "text-sm text-red-600"}>
              {status.message}
            </p>
          ) : null}

          {tenantId === null ? <p className="text-sm text-red-600">Tenant inválido.</p> : null}
          {tenantMismatch ? <p className="text-sm text-red-600">Tenant não autorizado para o usuário autenticado.</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Entregadores</CardTitle>
        </CardHeader>
        <CardContent>
          {listQuery.isLoading ? <p className="text-sm text-slate-500">Carregando entregadores...</p> : null}
          {listQuery.isError ? (
            <p className="text-sm text-red-600">
              {listQuery.error instanceof ApiError ? listQuery.error.message : "Erro ao carregar entregadores."}
            </p>
          ) : null}

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead>Telefone</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {listQuery.data?.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>{user.name}</TableCell>
                  <TableCell>{user.phone}</TableCell>
                  <TableCell>
                    <Badge variant={user.active ? "success" : "secondary"}>{user.active ? "Ativo" : "Inativo"}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="outline" onClick={() => openEditModal(user)}>
                        <Pencil className="mr-2 h-4 w-4" />
                        Editar
                      </Button>
                      <Button
                        size="sm"
                        variant={user.active ? "outline" : "default"}
                        onClick={() => toggleMutation.mutate({ id: user.id, active: !user.active })}
                        disabled={toggleMutation.isPending}
                      >
                        {user.active ? "Desativar" : "Ativar"}
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!listQuery.isLoading && (listQuery.data?.length ?? 0) === 0 ? (
                <TableRow>
                  <TableCell className="text-sm text-slate-500" colSpan={4}>
                    Nenhum entregador cadastrado para este tenant.
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {isModalOpen ? (
        <div className="fixed inset-0 z-[10010] flex items-center justify-center p-4">
          <button
            type="button"
            aria-label="Fechar modal"
            className="absolute inset-0 bg-slate-950/50"
            onClick={closeModal}
            disabled={isSaving}
          />

          <div className="relative z-10 w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-slate-900">
              {editingUser ? "Editar entregador" : "Novo Entregador"}
            </h2>
            <p className="mt-1 text-sm text-slate-500">Preencha os dados para salvar o entregador.</p>

            <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="delivery-user-name">
                  Nome
                </label>
                <Input
                  id="delivery-user-name"
                  value={form.name}
                  onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                  required
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="delivery-user-phone">
                  Telefone
                </label>
                <Input
                  id="delivery-user-phone"
                  value={form.phone}
                  onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))}
                  required
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="delivery-user-password">
                  Senha
                </label>
                <Input
                  id="delivery-user-password"
                  type="password"
                  minLength={6}
                  value={form.password}
                  onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                  placeholder={editingUser ? "Deixe em branco para manter a senha atual" : "Mínimo de 6 caracteres"}
                  required={!editingUser}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700" htmlFor="delivery-user-status">
                  Status
                </label>
                <Select
                  id="delivery-user-status"
                  value={form.active ? "active" : "inactive"}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      active: event.target.value === "active",
                    }))
                  }
                >
                  <option value="active">Ativo</option>
                  <option value="inactive">Inativo</option>
                </Select>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={closeModal} disabled={isSaving}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={isSaving || meLoading}>
                  {isSaving ? "Salvando..." : editingUser ? "Salvar alterações" : "Criar entregador"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
