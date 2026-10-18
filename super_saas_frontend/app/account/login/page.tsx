"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { customerAccountUrl, customerTenant, requestCustomerCode } from "@/lib/customerAuth";
export default function CustomerLoginPage() {
  const [phone, setPhone] = useState("");
  const [terms, setTerms] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const submit = async () => {
    if (loading || !terms) return;
    setLoading(true); setError("");
    try {
      await requestCustomerCode(phone, terms);
      sessionStorage.setItem(`customer-auth-phone:${customerTenant()}`, phone);
      router.push(customerAccountUrl("/account/verify"));
    } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível enviar o código"); }
    finally { setLoading(false); }
  };
  return <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center p-6">
    <h1 className="text-2xl font-black">Acessar meus pedidos</h1>
    <p className="mt-2 text-sm text-slate-600">Confirme seu telefone por código para acessar seu histórico. Você pode comprar sem criar uma conta.</p>
    <label className="mt-6 text-sm font-semibold" htmlFor="customer-phone">Telefone</label>
    <input id="customer-phone" className="mt-2 rounded-xl border p-3" inputMode="tel" autoComplete="tel" value={phone} onChange={e => setPhone(e.target.value)} placeholder="(11) 99999-9999" />
    <label className="mt-4 flex gap-2 text-xs text-slate-600"><input type="checkbox" checked={terms} onChange={e => setTerms(e.target.checked)} />Aceito os termos e a política de privacidade para autenticação por telefone.</label>
    {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
    <button className="mt-5 rounded-xl bg-slate-950 p-3 font-bold text-white disabled:opacity-50" disabled={loading || !terms || phone.replace(/\D/g, "").length < 10} onClick={submit}>{loading ? "Enviando..." : "Receber código"}</button>
    <button className="mt-4 text-sm" onClick={() => router.push(`/loja/${encodeURIComponent(customerTenant())}`)}>Voltar ao cardápio</button>
  </main>;
}
