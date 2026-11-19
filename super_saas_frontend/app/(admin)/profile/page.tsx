"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingExperience } from "@/components/ui/loading-experience";
import { useSession } from "@/hooks/use-session";
import { api } from "@/lib/api";

interface TenantSummary {
  id: number;
  slug?: string | null;
  business_name?: string | null;
  name?: string | null;
}

function getInitial(name?: string | null, email?: string | null) {
  const source = name?.trim() || email?.trim() || "?";
  return source.slice(0, 1).toUpperCase();
}

function Field({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 break-words text-sm font-medium text-slate-900">{value}</dd>
    </div>
  );
}

export default function ProfilePage() {
  const { data: user, isLoading: isSessionLoading, refetch: refreshSession } = useSession();
  const [newEmail, setNewEmail] = useState("");
  const [password, setPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [emailMessage, setEmailMessage] = useState("");

  const tenantQuery = useQuery({
    queryKey: ["tenant", "profile-summary"],
    queryFn: () => api.get<TenantSummary>("/api/admin/tenant"),
    enabled: Boolean(user?.tenant_id),
    retry: false,
  });

  if (isSessionLoading) {
    return <LoadingExperience label="Preparando seu perfil" />;
  }

  if (!user) {
    return <p className="text-sm text-red-600">Não foi possível carregar o usuário autenticado.</p>;
  }

  const tenantName = tenantQuery.data?.business_name || tenantQuery.data?.name;
  const tenantValue = tenantName
    ? `${tenantName}${tenantQuery.data?.slug ? ` (${tenantQuery.data.slug})` : ""}`
    : `Tenant ${user.tenant_id}`;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-950">Meu perfil</h1>
        <p className="mt-1 text-sm text-slate-500">
          Dados da sessão administrativa atual. O proprietário pode corrigir um e-mail ainda não confirmado.
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xl font-semibold text-slate-700 shadow-inner">
              {getInitial(user.name, user.email)}
            </div>
            <div className="min-w-0">
              <CardTitle>{user.name || user.email}</CardTitle>
              <CardDescription className="truncate">{user.email}</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-3 sm:grid-cols-2">
            <Field label="Nome" value={user.name || "Não informado"} />
            <Field label="E-mail" value={user.email} />
            <Field label="Cargo/perfil" value={user.role || "Não informado"} />
            <Field label="Tenant/loja atual" value={tenantValue} />
            <Field label="ID do usuário" value={user.id} />
            <Field label="Status" value={user.active ? "Ativo" : "Inativo"} />
          </dl>
          {tenantQuery.isError ? (
            <p className="mt-4 text-sm text-slate-600">
              Perfil carregado pela sessão atual, mas os detalhes da loja não puderam ser obtidos agora.
            </p>
          ) : null}
        </CardContent>
      </Card>
      {user.role === "owner" && user.email_verification_required && !user.email_verified &&
        <Card id="email"><CardHeader><CardTitle>Corrigir e-mail de acesso</CardTitle><CardDescription>Use esta opção se digitou o endereço errado. Confirme sua senha para receber um novo link.</CardDescription></CardHeader>
          <CardContent><form className="space-y-3" onSubmit={async e => { e.preventDefault(); if (saving) return; setSaving(true); setEmailMessage(""); try {
            await api.post("/api/admin/auth/email-verification/change", { email: newEmail, password }, { "X-Email-Action": "1" });
            setPassword(""); setNewEmail(""); setEmailMessage("Enviamos um novo link de confirmação para o endereço corrigido."); await refreshSession();
          } catch { setEmailMessage("Não foi possível corrigir o e-mail. Confira a senha e tente novamente."); } finally { setSaving(false); } }}>
            <label className="block text-sm">Novo e-mail<input type="email" required maxLength={320} autoComplete="email" value={newEmail} onChange={e => setNewEmail(e.target.value)} className="mt-1 w-full rounded border p-3" /></label>
            <label className="block text-sm">Senha atual<input type="password" required autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} className="mt-1 w-full rounded border p-3" /></label>
            <button disabled={saving} className="rounded bg-red-600 px-4 py-3 font-semibold text-white disabled:opacity-50">{saving ? "Salvando..." : "Corrigir e reenviar link"}</button>
            {emailMessage && <p role="status" className="text-sm">{emailMessage}</p>}
          </form></CardContent>
        </Card>}
    </div>
  );
}
