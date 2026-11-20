"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { customerAccountUrl, customerTenant, requestCustomerEmailCode } from "@/lib/customerAuth";
export default function CustomerLoginPage() {
  const [email, setEmail] = useState("");
  const [terms, setTerms] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const submit = async () => {
    if (loading || !terms) return;
    setLoading(true); setError("");
    try {
      await requestCustomerEmailCode(email, terms);
      sessionStorage.setItem(`customer-auth-email:${customerTenant()}`, email.trim().toLowerCase());
      router.push(customerAccountUrl("/account/verify"));
    } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível enviar o código"); }
    finally { setLoading(false); }
  };
  return <main className="mx-auto flex min-h-[calc(100dvh-var(--customer-bottom-nav-height)-var(--customer-safe-bottom)-16px)] max-w-md flex-col justify-center p-6">
    <h1 className="text-2xl font-black">Acessar meus pedidos</h1>
    <p className="mt-2 text-sm text-slate-600">Enviaremos um código ao seu e-mail para acessar seus pedidos. Você pode comprar sem criar uma conta.</p>
    <label className="mt-6 text-sm font-semibold" htmlFor="customer-email">E-mail usado nos pedidos</label>
    <input id="customer-email" className="mt-2 rounded-xl border p-3" type="email" inputMode="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="voce@exemplo.com" />
    <label className="mt-4 flex gap-2 text-xs text-slate-600"><input type="checkbox" checked={terms} onChange={e => setTerms(e.target.checked)} />Aceito os termos e a política de privacidade para autenticação por e-mail.</label>
    {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
    <button className="mt-5 rounded-xl bg-slate-950 p-3 font-bold text-white disabled:opacity-50" disabled={loading || !terms || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())} onClick={submit}>{loading ? "Enviando..." : "Receber código por e-mail"}</button>
    <button className="mt-4 text-sm" onClick={() => router.push(`/loja/${encodeURIComponent(customerTenant())}`)}>Voltar ao cardápio</button>
  </main>;
}
