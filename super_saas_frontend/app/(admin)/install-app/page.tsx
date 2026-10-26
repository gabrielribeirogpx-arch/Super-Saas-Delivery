"use client";

import { useState } from "react";
import { CheckCircle2, Download, ExternalLink, Smartphone } from "lucide-react";
import { useAdminPwaInstall } from "@/components/pwa/AdminPwaProvider";

export default function InstallAppPage() {
  const { ready, installed, canPrompt, install } = useAdminPwaInstall();
  const [dismissed, setDismissed] = useState(false);

  return (
    <div className="mx-auto max-w-3xl space-y-6 pb-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.15em] text-brand-700">Minha Loja</p>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">Fomizero no seu celular</h1>
        <p className="mt-2 max-w-xl text-sm leading-6 text-slate-600">Acesse pedidos, cozinha e gestão direto da tela inicial. A instalação é opcional e usa o navegador do celular.</p>
      </div>

      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center gap-4 border-b border-slate-100 bg-gradient-to-r from-red-50 to-white p-5 sm:p-7">
          <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-red-600 text-white shadow-lg shadow-red-200"><Smartphone className="h-8 w-8" /></div>
          <div><h2 className="text-lg font-bold text-slate-950">Fomizero Gestão</h2><p className="text-sm text-slate-600">Seu painel, a um toque de distância.</p></div>
        </div>
        <div className="space-y-4 p-5 sm:p-7">
          {installed ? (
            <p className="flex items-center gap-2 font-semibold text-emerald-700" role="status"><CheckCircle2 className="h-5 w-5" /> O app já está aberto como aplicativo neste aparelho.</p>
          ) : canPrompt ? (
            <button type="button" onClick={async () => setDismissed((await install()) === "dismissed")} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-red-600 px-6 text-sm font-bold text-white transition hover:bg-red-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600"><Download className="h-4 w-4" /> Instalar no celular</button>
          ) : ready ? (
            <p className="text-sm text-slate-600">A instalação pelo botão ainda não está disponível neste navegador. Use as instruções abaixo.</p>
          ) : null}
          {dismissed && <p className="text-sm text-slate-600" role="status">Tudo bem. Você pode instalar depois pelo menu do navegador.</p>}
          <p className="text-xs leading-5 text-slate-500">Não há arquivo APK para baixar. O navegador cria o ícone do app e mantém o acesso ao painel protegido pelo seu login.</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-bold text-slate-950">Android · Chrome</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">Toque em <strong>Instalar no celular</strong> acima. Se o botão não aparecer, abra o menu <strong>⋮</strong> do Chrome e escolha <strong>Instalar app</strong> ou <strong>Adicionar à tela inicial</strong>.</p>
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-bold text-slate-950">iPhone · Safari</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">Abra esta página no Safari, toque em <strong>Compartilhar</strong> e depois em <strong>Adicionar à Tela de Início</strong>. Confirme em <strong>Adicionar</strong>.</p>
        </section>
      </div>
      <p className="flex items-start gap-2 text-xs leading-5 text-slate-500"><ExternalLink className="mt-0.5 h-4 w-4 shrink-0" /> O app precisa de internet para carregar pedidos e dados atuais. Seu cardápio público e o app do entregador continuam separados.</p>
    </div>
  );
}
