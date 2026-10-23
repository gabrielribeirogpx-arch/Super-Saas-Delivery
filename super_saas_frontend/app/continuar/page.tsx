"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { buildTenantPublicUrl } from "@/lib/platformDomains";
import { recentStore } from "@/lib/recentStore";
export default function ContinuePage() {
  const [slug, setSlug] = useState("");
  useEffect(() => { setSlug(recentStore()); }, []);
  return <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6"><section className="w-full max-w-lg space-y-5 rounded-2xl border bg-white p-8"><h1 className="text-2xl font-semibold">Continue na sua loja</h1><p>Entre no Fomizero para consultar sua assinatura e preparar seu restaurante.</p><p className="text-sm text-slate-600">A liberação acontece após a confirmação do pagamento pela Hotmart e pode levar alguns minutos. Esta página não confirma uma compra.</p>{slug && <a className="block rounded bg-red-600 p-3 text-center font-semibold text-white" href={buildTenantPublicUrl(slug, "/login?redirect=/subscriptions")}>Entrar na minha loja</a>}<Link className="block text-center text-sm underline" href="/entrar?assinatura=1">{slug ? "Usar outra loja" : "Informar minha loja"}</Link><p className="text-sm text-slate-600">Se você já pagou, consulte o status antes de realizar outra compra.</p></section></main>;
}
