"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { customerAccountUrl, customerTenant, requestCustomerEmailCode } from "@/lib/customerAuth";
export default function CustomerLoginPage() {
  const [mode, setMode] = useState<"signup" | "login">("signup");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [terms, setTerms] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const submit = async () => {
    if (loading || (mode === "signup" && !terms)) return;
    setLoading(true); setError("");
    try {
      await requestCustomerEmailCode(email, mode === "signup" && terms, mode === "signup" ? { name: name.trim(), phone } : undefined);
      sessionStorage.setItem(`customer-auth-email:${customerTenant()}`, email.trim().toLowerCase());
      router.push(customerAccountUrl("/account/verify"));
    } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível enviar o código"); }
    finally { setLoading(false); }
  };
  return <main className="mx-auto flex min-h-[calc(100dvh-var(--customer-bottom-nav-height)-var(--customer-safe-bottom)-16px)] max-w-md flex-col justify-center p-6">
    <h1 className="text-2xl font-black">{mode === "signup" ? "Criar minha conta" : "Entrar na minha conta"}</h1>
    <p className="mt-2 text-sm text-slate-600">{mode === "signup" ? "Cadastre seus dados para acompanhar pedidos desta loja. Você pode comprar sem criar uma conta." : "Enviaremos um código ao e-mail cadastrado para entrar."}</p>
    {mode === "signup" && <>
      <label className="mt-6 text-sm font-semibold" htmlFor="customer-name">Seu nome</label>
      <input id="customer-name" className="mt-2 rounded-xl border p-3" autoComplete="name" value={name} onChange={e => setName(e.target.value)} placeholder="Como podemos chamar você?" />
      <label className="mt-4 text-sm font-semibold" htmlFor="customer-phone">Celular para contato</label>
      <input id="customer-phone" className="mt-2 rounded-xl border p-3" type="tel" inputMode="tel" autoComplete="tel" value={phone} onChange={e => setPhone(e.target.value)} placeholder="(11) 99999-9999" />
    </>}
    <label className={`${mode === "signup" ? "mt-4" : "mt-6"} text-sm font-semibold`} htmlFor="customer-email">E-mail {mode === "login" ? "cadastrado" : "para confirmar a conta"}</label>
    <input id="customer-email" className="mt-2 rounded-xl border p-3" type="email" inputMode="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="voce@exemplo.com" />
    {mode === "signup" && <label className="mt-4 flex gap-2 text-xs text-slate-600"><input type="checkbox" checked={terms} onChange={e => setTerms(e.target.checked)} />Aceito os termos e a política de privacidade para criar minha conta.</label>}
    {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
    <button className="mt-5 rounded-xl bg-slate-950 p-3 font-bold text-white disabled:opacity-50" disabled={loading || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) || (mode === "signup" && (!terms || name.trim().length < 2 || phone.replace(/\D/g, "").length < 10))} onClick={submit}>{loading ? "Enviando..." : mode === "signup" ? "Confirmar e-mail e criar conta" : "Receber código para entrar"}</button>
    <button className="mt-3 text-sm underline" onClick={() => { setMode(mode === "signup" ? "login" : "signup"); setError(""); }}>{mode === "signup" ? "Já tenho conta" : "Criar conta"}</button>
    <button className="mt-4 text-sm" onClick={() => router.push(`/loja/${encodeURIComponent(customerTenant())}`)}>Voltar ao cardápio</button>
  </main>;
}
