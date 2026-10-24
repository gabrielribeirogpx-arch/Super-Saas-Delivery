"use client";
import Image from "next/image";
import Link from "next/link";
import fomizeroLogo from "../../public/fomizero-logo.svg";
import { useEffect, useState } from "react";
import { buildTenantPublicUrl, RESERVED_PLATFORM_SUBDOMAINS } from "@/lib/platformDomains";
import { recentStore } from "@/lib/recentStore";
export default function FindStorePage() {
  const [slug, setSlug] = useState(""); const [error, setError] = useState("");
  const [resume, setResume] = useState(false);
  useEffect(() => { setSlug(recentStore()); setResume(new URLSearchParams(window.location.search).get("assinatura") === "1"); }, []);
  return <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6"><form className="w-full max-w-md space-y-5 rounded-2xl border bg-white p-8" onSubmit={e => { e.preventDefault(); const value = slug.trim().toLowerCase(); if (!/^[a-z0-9](?:[a-z0-9-]{1,78}[a-z0-9])?$/.test(value) || RESERVED_PLATFORM_SUBDOMAINS.has(value)) return setError("Informe o identificador da sua loja, sem pontos ou barras."); window.location.assign(buildTenantPublicUrl(value, resume ? "/login?redirect=/subscriptions" : "/login")); }}>
    <div className="flex justify-center"><Image src={fomizeroLogo} alt="Fomizero" width={190} height={50} className="h-auto w-[145px] object-contain sm:w-[170px] md:w-[190px]" priority /></div>
    <h1 className="text-2xl font-semibold">Entre na sua loja</h1><label className="block text-sm" htmlFor="store-slug">Identificador da loja</label><input id="store-slug" required maxLength={80} autoComplete="organization" className="w-full rounded border p-3" placeholder="minha-pizzaria" value={slug} onChange={e => setSlug(e.target.value)} /><p className="text-sm text-slate-600">Use a parte do endereço que vem antes do domínio Fomizero.</p>{error && <p role="alert" className="text-sm text-red-700">{error}</p>}<button className="w-full rounded bg-red-600 p-3 font-semibold text-white">Continuar para login</button><Link className="block text-center text-sm underline" href="/assine">Conhecer os planos</Link>
  </form></main>;
}
