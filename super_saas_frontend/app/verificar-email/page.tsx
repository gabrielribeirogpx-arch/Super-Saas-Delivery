"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { buildTenantPublicUrl } from "@/lib/platformDomains";

export default function VerifyEmailPage() {
  const [state, setState] = useState<"checking" | "success" | "error">("checking");
  const [slug, setSlug] = useState("");
  useEffect(() => {
    const token = new URLSearchParams(window.location.hash.slice(1)).get("token");
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    if (!token) { setState("error"); return; }
    api.post<{ slug: string; verified: boolean }>("/api/onboarding/verify-email", { token })
      .then(result => { setSlug(result.slug); setState("success"); })
      .catch(() => setState("error"));
  }, []);
  return <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6"><section className="w-full max-w-md space-y-4 rounded-xl border bg-white p-8 text-center">
    <h1 className="text-2xl font-semibold">Confirmação de e-mail</h1>
    {state === "checking" && <p role="status">Confirmando seu endereço...</p>}
    {state === "success" && <><p role="status">E-mail confirmado. Sua loja poderá receber pedidos quando a assinatura estiver ativa.</p><a className="block rounded bg-red-600 p-3 font-semibold text-white" href={buildTenantPublicUrl(slug, "/login?redirect=/subscriptions")}>Entrar na minha loja</a></>}
    {state === "error" && <><p role="alert">O link é inválido ou expirou. Entre na sua loja para solicitar outro.</p><Link className="underline" href="/entrar?assinatura=1">Encontrar minha loja</Link></>}
  </section></main>;
}
