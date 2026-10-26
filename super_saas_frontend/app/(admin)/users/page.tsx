"use client";
import { usePlanAccess } from "@/hooks/use-plan-access";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { LoadingExperience } from "@/components/ui/loading-experience";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useSession } from "@/hooks/use-session";

interface AdminUser {
  id: number;
  tenant_id: number;
  email: string;
  name: string;
  role: string;
  active: boolean;
}

export default function UsersPage() {
  const plan = usePlanAccess();
  const seatBlocked = Boolean(plan.data?.managed && !plan.data.features.admin_users?.allowed);
  const queryClient = useQueryClient();
  const { data: session } = useSession();
  const [form, setForm] = useState({
    email: "",
    name: "",
    role: "admin",
    password: "",
  });

  const { data: users, isLoading, isError } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => api.get<AdminUser[]>(`/api/admin/users`),
  });

  const createMutation = useMutation({
    mutationFn: () => {
      if (!session?.tenant_id) {
        throw new Error("Sessão indisponível");
      }
      return api.post<AdminUser>("/api/admin/users", {
        ...form,
        tenant_id: session.tenant_id,
      });
    },
    onSuccess: () => {
      setForm({ email: "", name: "", role: "admin", password: "" });
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<AdminUser> }) =>
      api.put(`/api/admin/users/${id}`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
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
          {seatBlocked && <p className="text-sm text-slate-700">Limite de usuários atingido ou assinatura inativa. O proprietário conta como um usuário. Confira sua assinatura.</p>}
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
            <Button disabled={createMutation.isPending || !session?.tenant_id || seatBlocked || plan.isPending} onClick={() => createMutation.mutate()}>
              {createMutation.isPending ? "Criando..." : "Criar usuário"}
            </Button>
            {createMutation.isError && (
              <p role="alert" className="mt-2 text-sm text-red-600">
                Não foi possível criar o usuário. Confira os campos e tente novamente.
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Usuários existentes</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <LoadingExperience label="Buscando usuários" compact />}
          {isError && (
            <p className="text-sm text-red-600">Erro ao carregar usuários.</p>
          )}
          <Table mobileCards>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Nome</TableHead>
                <TableHead>Perfil</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users?.map((user) => (
                <TableRow key={user.id}>
                  <TableCell mobileLabel="Email">{user.email}</TableCell>
                  <TableCell mobileLabel="Nome">{user.name}</TableCell>
                  <TableCell mobileLabel="Perfil">{user.role}</TableCell>
                  <TableCell mobileLabel="Status">{user.active ? "Ativo" : "Inativo"}</TableCell>
                  <TableCell mobileLabel="Ações" mobileActions className="space-x-2">
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
