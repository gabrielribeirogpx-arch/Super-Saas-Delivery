"use client";

import { useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { RequestErrorState } from "@/components/request-error-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";

const endpoint = "/api/admin/store/fiscal/focus";
const addressFields = [
  ["logradouro", "Logradouro", 120],
  ["numero", "Número", 60],
  ["bairro", "Bairro", 80],
  ["municipio", "Município", 80],
  ["cep", "CEP", 9],
] as const;
const productFields = [
  ["id", "ID do produto", "[1-9][0-9]*"],
  ["codigo_ncm", "NCM", "[0-9]{8}"],
  ["cfop", "CFOP", "5[0-9]{3}"],
  ["icms_origem", "Origem do ICMS", "[0-8]"],
  ["icms_situacao_tributaria", "CSOSN", "102|103|300|400"],
  ["pis_situacao_tributaria", "CST do PIS", "0[4-9]"],
  ["cofins_situacao_tributaria", "CST da COFINS", "0[4-9]"],
  ["unidade_comercial", "Unidade comercial", "[A-Z0-9]{1,6}"],
] as const;

interface TestResult {
  ref: string;
  status: string;
  status_sefaz?: string;
  mensagem_sefaz?: string;
  chave_nfe?: string;
}

function ActionError({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.status !== 401 && error.status !== 403) {
    return <p role="alert" className="text-sm text-red-700">{error.message}</p>;
  }
  if (error instanceof Error && !(error instanceof ApiError)) {
    return <p role="alert" className="text-sm text-red-700">{error.message}</p>;
  }
  return error ? <RequestErrorState error={error} /> : null;
}

function ConnectForm({ onConnected }: { onConnected: () => void }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setPending(true);
    setError(null);
    try {
      const file = data.get("certificado");
      if (!(file instanceof File) || !file.size || file.size > 65_000) {
        throw new Error("Escolha um certificado A1 .pfx ou .p12 de até 65 KB.");
      }
      const bytes = new Uint8Array(await file.arrayBuffer());
      const certificado = btoa(Array.from(bytes, (byte) => String.fromCharCode(byte)).join(""));
      const address = Object.fromEntries(addressFields.map(([name]) => [name, data.get(name)]));
      await api.post(endpoint + "/connect", {
        ...address, certificado, senha: data.get("senha"),
        csc: data.get("csc") || null,
        id_csc: data.get("id_csc") ? Number(data.get("id_csc")) : null,
      });
      onConnected();
    } catch (failure) {
      setError(failure);
    } finally {
      for (const name of ["certificado", "senha", "csc"]) {
        const input = form.elements.namedItem(name);
        if (input instanceof HTMLInputElement) input.value = "";
      }
      setPending(false);
    }
  }

  return (
    <form className="space-y-4" onSubmit={submit}>
      <p className="text-sm text-slate-600">
        Use o A1 do CNPJ cadastrado. Informe o CSC e seu ID de homologação quando a SEFAZ da sua UF exigir.
      </p>
      <fieldset disabled={pending} className="grid gap-4 sm:grid-cols-2">
        {addressFields.map(([name, label, maxLength]) => (
          <label key={name} className="space-y-1 text-sm">
            <span>{label}</span><Input required name={name} maxLength={maxLength} />
          </label>
        ))}
        <label className="space-y-1 text-sm">
          <span>Certificado A1</span><Input required name="certificado" type="file" accept=".pfx,.p12" />
        </label>
        <label className="space-y-1 text-sm">
          <span>Senha do A1</span><Input name="senha" type="password" autoComplete="new-password" maxLength={256} />
        </label>
        <label className="space-y-1 text-sm">
          <span>CSC de homologação</span><Input name="csc" type="password" autoComplete="off" maxLength={128} />
        </label>
        <label className="space-y-1 text-sm">
          <span>ID do CSC</span><Input name="id_csc" inputMode="numeric" pattern="[0-9]{1,6}" />
        </label>
      </fieldset>
      <ActionError error={error} />
      <Button disabled={pending} type="submit">
        {pending ? "Conectando…" : "Conectar emissão fiscal"}
      </Button>
    </form>
  );
}

function TestForm() {
  const [rows, setRows] = useState(1);
  const issue = useMutation({
    mutationFn: ({ order_id, products }: { order_id: number; products: Record<string, Record<string, string>> }) =>
      api.post<TestResult>(endpoint + "/test", { order_id, products }),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const products: Record<string, Record<string, string>> = {};
    for (let row = 0; row < rows; row += 1) {
      const entries = productFields.map(([name]) => [name, String(data.get(row + "-" + name))]);
      const [[, id], ...fields] = entries;
      products[id] = Object.fromEntries(fields);
    }
    issue.mutate({ order_id: Number(data.get("order_id")), products });
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-sm text-slate-600">
        Use um pedido de mesa concluído, pago em dinheiro, sem troco, descontos ou adicionais.
        Preencha os códigos fiscais aprovados pela contabilidade. A NFC-e de homologação é sem validade fiscal.
      </p>
      <fieldset disabled={issue.isPending} className="space-y-4">
        <label className="block max-w-xs space-y-1 text-sm">
          <span>ID interno do pedido de teste</span>
          <Input required name="order_id" inputMode="numeric" pattern="[1-9][0-9]*" />
        </label>
        {Array.from({ length: rows }, (_, row) => (
          <fieldset key={row} className="grid gap-3 rounded-lg border border-slate-200 p-3 sm:grid-cols-2">
            <legend className="px-1 text-sm font-medium">Dados fiscais do produto</legend>
            {productFields.map(([name, label, pattern]) => (
              <label key={name} className="space-y-1 text-sm">
                <span>{label}</span><Input required name={row + "-" + name} pattern={pattern} />
              </label>
            ))}
          </fieldset>
        ))}
        <div className="flex flex-wrap gap-2">
          {rows < 100 && <Button type="button" variant="outline" onClick={() => setRows(rows + 1)}>Adicionar produto</Button>}
          {rows > 1 && <Button type="button" variant="outline" onClick={() => setRows(rows - 1)}>Remover último produto</Button>}
        </div>
      </fieldset>
      <ActionError error={issue.error} />
      {issue.data && (
        <div role="status" className="space-y-1 break-words rounded-lg bg-slate-50 p-3 text-sm">
          <p className="font-semibold">{issue.data.status === "autorizado" ? "Autorizada em homologação" : issue.data.status}</p>
          <p>Referência {issue.data.ref}</p>
          {issue.data.mensagem_sefaz && <p>{issue.data.mensagem_sefaz}</p>}
          {issue.data.chave_nfe && <p>Chave {issue.data.chave_nfe}</p>}
        </div>
      )}
      <Button type="submit" disabled={issue.isPending}>
        {issue.isPending ? "Consultando a Focus…" : "Emitir ou consultar NFC-e de teste"}
      </Button>
    </form>
  );
}

export function FocusPanel({ tenantId }: { tenantId: number }) {
  const connection = useQuery({
    queryKey: ["tenant", tenantId, "focus-connection"],
    queryFn: () => api.get<{ available: boolean; connected: boolean }>(endpoint),
  });

  return (
    <Card>
      <CardHeader><CardTitle>Emissão fiscal em homologação</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        {connection.isError ? <RequestErrorState error={connection.error} />
          : connection.isPending ? <p role="status" className="text-sm">Consultando conexão…</p>
          : !connection.data.available ? <p className="text-sm">A integração ainda aguarda habilitação no servidor.</p>
          : connection.data.connected ? <><p className="text-sm font-medium">Emitente conectado à Focus NFe</p><TestForm /></>
          : <ConnectForm onConnected={() => { void connection.refetch(); }} />}
      </CardContent>
    </Card>
  );
}
