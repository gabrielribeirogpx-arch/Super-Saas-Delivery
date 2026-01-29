"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";

interface AdminUser {
  id: number;
  tenant_id: number;
  email: string;
  name: string;
  role: string;
  active: boolean;
}

export default function UsersPage({ params }: { params: { tenantId: string } }) {
  const tenantId = params.tenantId;
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    email: "",
    name: "",
    role: "admin",
    password: "",
  });

  const { data: users, isLoading, isError } = useQuery({
    queryKey: ["admin-users", tenantId],
    queryFn: () => api.get<AdminUser[]>(`/api/admin/users?tenant_id=${tenantId}`),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post<AdminUser>("/api/admin/users", {
        tenant_id: Number(tenantId),
        ...form,
      }),
    onSuccess: () => {
      setForm({ email: "", name: "", role: "admin", password: "" });
      queryClient.invalidateQueries({ queryKey: ["admin-users", tenantId] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<AdminUser> }) =>
      api.put(`/api/admin/users/${id}`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users", tenantId] }),
  });

  const resetMutation = useMutation({
    mutationFn: ({ id, password }: { id: number; password: string }) =>
      api.post(`/api/admin/users/${id}/reset_password`, { new_password: password }),
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Novo usuário</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-4">
          <Input
            placeholder="Email"
            value={form.email}
            onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
          />
          <Input
            placeholder="Nome"
            value={form.name}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
          />
          <Select
            value={form.role}
            onChange={(e) => setForm((prev) => ({ ...prev, role: e.target.value }))}
          >
            <option value="admin">Admin</option>
            <option value="operator">Operador</option>
            <option value="cashier">Caixa</option>
          </Select>
          <Input
            placeholder="Senha"
            type="password"
            value={form.password}
            onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
          />
          <div className="md:col-span-4">
            <Button onClick={() => createMutation.mutate()}>
              {createMutation.isPending ? "Criando..." : "Criar usuário"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Usuários existentes</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <p className="text-sm text-slate-500">Carregando usuários...</p>}
          {isError && (
            <p className="text-sm text-red-600">Erro ao carregar usuários.</p>
          )}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Nome</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users?.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>{user.name}</TableCell>
                  <TableCell>{user.role}</TableCell>
                  <TableCell>{user.active ? "Ativo" : "Inativo"}</TableCell>
                  <TableCell className="space-x-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        updateMutation.mutate({
                          id: user.id,
                          payload: { active: !user.active },
                        })
                      }
                    >
                      {user.active ? "Desativar" : "Ativar"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        const newPassword = window.prompt(
                          `Nova senha para ${user.email}`,
                          ""
                        );
                        if (newPassword) {
                          resetMutation.mutate({ id: user.id, password: newPassword });
                        }
                      }}
                    >
                      Reset senha
                    </Button>
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
