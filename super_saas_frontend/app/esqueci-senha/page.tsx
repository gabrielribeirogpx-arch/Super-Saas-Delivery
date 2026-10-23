"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { extractPlatformTenantSlug } from "@/lib/platformDomains";
export default function ForgotPasswordPage() {
  const [slug,setSlug]=useState(""); const [email,setEmail]=useState(""); const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState(""); const [error,setError]=useState("");
  useEffect(()=>{setSlug(extractPlatformTenantSlug(window.location.hostname)??"");},[]);
  return <main className="flex min-h-screen items-center justify-center bg-slate-50 p-5"><section className="w-full max-w-md space-y-5 rounded-xl border bg-white p-7"><h1 className="text-2xl font-semibold">Recupere seu acesso</h1><p className="text-sm">Informe o e-mail que usa para entrar na sua loja. Enviaremos um link para criar uma nova senha.</p><form className="space-y-4" onSubmit={async e=>{e.preventDefault();if(busy)return;setBusy(true);setError("");try{const result=await api.post<{message:string}>("/api/admin/auth/forgot-password",{tenant_slug:slug.trim().toLowerCase(),email:email.trim()});setMessage(result.message);}catch{setError("Não foi possível solicitar o link agora. Aguarde um minuto e tente novamente.");}finally{setBusy(false);}}}>
    <label className="grid gap-1 text-sm">Identificador da loja<input required maxLength={80} pattern="[a-z0-9][a-z0-9-]*" className="rounded border p-3" value={slug} onChange={e=>setSlug(e.target.value)} placeholder="minha-pizzaria" /></label><label className="grid gap-1 text-sm">E-mail de acesso<input type="email" required autoComplete="email" className="rounded border p-3" value={email} onChange={e=>setEmail(e.target.value)} /></label><button disabled={busy} className="w-full rounded bg-red-600 p-3 font-semibold text-white">{busy?"Solicitando...":"Enviar link de recuperação"}</button></form>{message&&<p role="status" className="text-sm text-emerald-800">{message}</p>}{error&&<p role="alert" className="text-sm text-red-700">{error}</p>}<Link href="/login" className="block text-center text-sm underline">Voltar ao login</Link></section></main>;
}
