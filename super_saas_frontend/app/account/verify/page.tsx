"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { customerAccountUrl, customerTenant, requestCustomerCode, verifyCustomerCode } from "@/lib/customerAuth";
export default function VerifyPage() {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(60);
  const router = useRouter();
  useEffect(() => { setPhone(sessionStorage.getItem(`customer-auth-phone:${customerTenant()}`) || ""); }, []);
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown(value => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);
  const confirm = async () => {
    if (busy || code.length !== 6 || !phone) return;
    setBusy(true); setError("");
    try { await verifyCustomerCode(phone, code); router.replace(customerAccountUrl("/account/orders")); }
    catch (e) { setError(e instanceof Error ? e.message : "Código inválido"); }
    finally { setBusy(false); }
  };
  const resend = async () => {
    if (busy || cooldown > 0 || !phone) return;
    setBusy(true); setError("");
    try { await requestCustomerCode(phone, true); setCooldown(60); }
    catch (e) { setError(e instanceof Error ? e.message : "Não foi possível reenviar"); }
    finally { setBusy(false); }
  };
  return <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center p-6">
    <h1 className="text-2xl font-black">Digite o código</h1>
    <p className="mt-2 text-sm text-slate-600">Informe o código de seis dígitos enviado ao telefone informado.</p>
    <input aria-label="Código de acesso" className="mt-6 rounded-xl border p-4 text-center text-2xl tracking-widest" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} />
    {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
    <button disabled={busy || !phone || code.length !== 6} className="mt-5 rounded-xl bg-slate-950 p-3 font-bold text-white disabled:opacity-50" onClick={confirm}>Confirmar código</button>
    <button disabled={busy || !phone || cooldown > 0} className="mt-3 text-sm" onClick={resend}>{cooldown > 0 ? `Reenviar em ${cooldown}s` : "Reenviar código"}</button>
    <button className="mt-3 text-sm" onClick={() => router.replace(customerAccountUrl("/account/login"))}>Alterar telefone</button>
  </main>;
}
