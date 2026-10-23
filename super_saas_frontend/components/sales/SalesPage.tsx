"use client";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SalesConfig } from "@/lib/sales";
import { subscriptionFeatureNames } from "@/lib/subscriptions";
import logo from "../../public/fomizero-logo.svg";
export default function SalesPage() {
  const [config, setConfig] = useState<SalesConfig | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => { api.get<SalesConfig>("/api/onboarding/sales-config").then(setConfig).catch(() => setError(true)); }, []);
  return <main className="min-h-screen bg-slate-50 text-slate-900">
    <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6" aria-label="Principal"><Image src={logo} alt="Fomizero Delivery" width={180} height={55} priority /><Link className="rounded-lg border bg-white px-5 py-3 text-sm" href="/entrar">Entrar na minha loja</Link></nav>
    <section className="mx-auto max-w-4xl px-6 py-14 text-center"><p className="mb-4 font-semibold text-red-600">DO CARDÁPIO À ENTREGA</p><h1 className="text-4xl font-bold leading-tight sm:text-6xl">Sua operação de delivery em um só lugar.</h1><p className="mx-auto mt-6 max-w-2xl text-lg text-slate-600">Organize cardápio, pedidos, cozinha, entregas e financeiro com o Fomizero. Escolha o plano para o tamanho do seu restaurante.</p><a href="#planos" className="mt-8 inline-block rounded-lg bg-red-600 px-7 py-4 font-semibold text-white">Conhecer os planos</a></section>
    <section className="mx-auto grid max-w-6xl gap-5 px-6 pb-12 md:grid-cols-3" aria-label="Como funciona">{[
      ["1. Crie sua loja", "Cadastre o restaurante e seu acesso de administrador."], ["2. Contrate seu plano", "Confira o valor mensal e conclua o pagamento no checkout da Hotmart."], ["3. Comece a configurar", "Após a confirmação do pagamento, os recursos do seu plano são liberados."],
    ].map(([title, text]) => <article key={title} className="rounded-xl border bg-white p-6"><h2 className="font-semibold">{title}</h2><p className="mt-2 text-sm text-slate-600">{text}</p></article>)}</section>
    <section id="planos" className="mx-auto max-w-6xl px-6 py-10"><h2 className="mb-8 text-center text-3xl font-bold">Um plano para sua próxima etapa</h2>
      {!config && <p role="status" className="text-center">{error ? "Não foi possível consultar os planos. Recarregue a página." : "Consultando planos..."}</p>}
      {config && !config.ready && <p role="status" className="mb-6 rounded-xl border bg-white p-5 text-center">As novas contratações ainda não estão disponíveis por aqui. Volte em breve.</p>}
      <div className="grid gap-5 md:grid-cols-3">{config?.offers.map(offer => <article key={offer.code} className="flex flex-col rounded-2xl border bg-white p-7 shadow-sm"><h3 className="text-xl font-semibold">{offer.name}</h3><p className="my-5"><strong className="text-3xl">{(offer.price_cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}</strong> / mês</p><ul className="mb-7 flex-1 space-y-3 text-sm"><li>Cardápio digital, pedidos, cozinha e financeiro</li>{offer.features.filter(f => f.enabled).map(f => <li key={f.code}>{subscriptionFeatureNames[f.code] ?? f.code}{f.limit !== null ? `: ${f.limit}` : ""}</li>)}</ul>{config.ready && <Link className="rounded-lg bg-red-600 px-5 py-3 text-center font-semibold text-white" href={`/onboarding?plan=${encodeURIComponent(offer.code)}`}>Escolher {offer.name}</Link>}</article>)}</div>
      <p className="mt-6 text-center text-sm text-slate-600">Assinatura mensal. O administrador proprietário conta como um usuário da equipe. Integrações externas exigem configuração e podem ter custos próprios.</p>
    </section>
    <section className="mx-auto max-w-3xl space-y-5 px-6 py-10"><h2 className="text-2xl font-semibold">Antes de começar</h2><details className="rounded-xl border bg-white p-5"><summary className="cursor-pointer font-medium">Criar a loja já inicia uma cobrança?</summary><p className="mt-3 text-sm">Não. O cadastro prepara seu acesso. Você escolhe um plano e confirma a assinatura na Hotmart. Os recursos pagos dependem da confirmação do pagamento.</p></details><details className="rounded-xl border bg-white p-5"><summary className="cursor-pointer font-medium">Como cancelo a renovação?</summary><p className="mt-3 text-sm">Na área Minha assinatura ou pelo portal de pagamentos da Hotmart. Após a confirmação do cancelamento, o período já pago continua disponível até seu término. Cancelar a renovação não solicita um reembolso.</p></details></section>
    <footer className="mx-auto flex max-w-6xl flex-wrap justify-center gap-6 border-t px-6 py-8 text-sm">{config?.terms_url && <a href={config.terms_url}>Termos de uso</a>}{config?.privacy_url && <a href={config.privacy_url}>Política de privacidade</a>}{config?.support_email && <a href={`mailto:${config.support_email}`}>Falar com o suporte</a>}<Link href="/entrar">Já sou cliente</Link></footer>
  </main>;
}
