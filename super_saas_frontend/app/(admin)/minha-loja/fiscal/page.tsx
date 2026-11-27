"use client";

import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { RequestErrorState } from "@/components/request-error-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LoadingExperience } from "@/components/ui/loading-experience";
import { useSession } from "@/hooks/use-session";
import { api, ApiError } from "@/lib/api";

interface FiscalProfile {
  cnpj: string;
  legal_name: string;
  state_registration: string;
  state_code: string;
  tax_regime: number;
}

const endpoint = "/api/admin/store/fiscal";
const states = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");
const textFields = [
  { name: "legal_name", label: "Razão social", maxLength: 120 },
  { name: "cnpj", label: "CNPJ", maxLength: 18 },
  { name: "state_registration", label: "Inscrição estadual", maxLength: 24 },
] as const;
const selectClass = "h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950";

function FiscalForm({ profile, tenantId }: { profile: FiscalProfile | null; tenantId: number }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FiscalProfile>(profile ?? {
    cnpj: "", legal_name: "", state_registration: "", state_code: "", tax_regime: 0,
  });
  const save = useMutation({
    mutationFn: (values: FiscalProfile) => api.put<FiscalProfile>(endpoint, values),
    onSuccess: (updated) => {
      queryClient.setQueryData(["tenant", tenantId, "fiscal-profile"], updated);
      setForm(updated);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    save.mutate(form);
  }

  return (
    <form className="space-y-4" onSubmit={submit} onChange={() => save.reset()}>
      <fieldset disabled={save.isPending} className="grid gap-4 sm:grid-cols-2">
        {textFields.map(({ name, label, maxLength }) => (
          <label key={name} className="space-y-1 text-sm font-medium text-slate-700">
            <span>{label}</span>
            <Input required maxLength={maxLength} value={form[name]}
              onChange={(event) => setForm({ ...form, [name]: event.target.value })} />
          </label>
        ))}
        <label className="space-y-1 text-sm font-medium text-slate-700">
          <span>UF da inscrição estadual</span>
          <select required className={selectClass} value={form.state_code}
            onChange={(event) => setForm({ ...form, state_code: event.target.value })}>
            <option value="">Selecione a UF</option>
            {states.map((state) => <option key={state}>{state}</option>)}
          </select>
        </label>
        <label className="space-y-1 text-sm font-medium text-slate-700 sm:col-span-2">
          <span>Código de Regime Tributário (CRT)</span>
          <select required className={selectClass} value={form.tax_regime || ""}
            onChange={(event) => setForm({ ...form, tax_regime: Number(event.target.value) })}>
            <option value="">Selecione o regime</option>
            <option value="1">1 · Simples Nacional</option>
            <option value="2">2 · Simples Nacional, excesso de sublimite</option>
            <option value="3">3 · Regime normal</option>
            <option value="4">4 · Microempreendedor Individual (MEI)</option>
          </select>
        </label>
      </fieldset>
      {save.isSuccess && <p role="status" className="text-sm text-emerald-700">Dados fiscais salvos.</p>}
      {save.error instanceof ApiError && save.error.status === 422
        ? <p role="alert" className="text-sm text-red-700">
            Confira o CNPJ, a razão social, a inscrição estadual, a UF e o regime tributário.
          </p>
        : save.isError && <RequestErrorState error={save.error} />}
      <Button type="submit" disabled={save.isPending}>
        {save.isPending ? "Salvando…" : "Salvar dados fiscais"}
      </Button>
    </form>
  );
}

export default function FiscalPage() {
  const { data: session } = useSession();
  const tenantId = session?.tenant_id;
  const profile = useQuery({
    queryKey: ["tenant", tenantId, "fiscal-profile"],
    queryFn: () => api.get<FiscalProfile | null>(endpoint),
    enabled: Boolean(tenantId),
  });

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-2 sm:px-6">
      <h1 className="text-2xl font-semibold text-slate-950">Fiscal</h1>
      <Card>
        <CardHeader>
          <CardTitle>Dados do emitente</CardTitle>
          <p className="text-sm text-slate-600">
            Cadastre os dados fiscais desta loja para preparar a integração com a NFC-e.
            A emissão depende da habilitação do provedor fiscal.
          </p>
        </CardHeader>
        <CardContent>
          {profile.isError ? <RequestErrorState error={profile.error} />
            : profile.isPending || !tenantId ? <LoadingExperience label="Carregando dados fiscais" compact />
            : <FiscalForm key={tenantId} profile={profile.data} tenantId={tenantId} />}
        </CardContent>
      </Card>
    </div>
  );
}
