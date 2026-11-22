"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronRight, Gift, LogOut, Mail, MapPin, Phone, ReceiptText, ShieldCheck, Sparkles } from "lucide-react";
import { customerMe, logoutCustomer, customerAccountUrl, customerTenant } from "@/lib/customerAuth";
type Customer = {
  name: string | null;
  verification_method: "phone" | "email";
  phone_masked?: string;
  email_masked?: string;
  loyalty?: { enabled: boolean; available_points: number; lifetime_points: number };
};
export default function Account() {
  const [me, setMe] = useState<Customer | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [tenant, setTenant] = useState("");
  const accountHref = (path: string) => tenant ? `${path}?tenant=${encodeURIComponent(tenant)}` : path;
  const router = useRouter();
  useEffect(() => {
    let active = true;
    setTenant(customerTenant());
    void customerMe().then(customer => {
      if (!active) return;
      if (customer) setMe(customer); else router.replace(customerAccountUrl("/account/login"));
    }).catch(() => { if (active) setError("Não foi possível carregar sua conta. Tente novamente."); });
    return () => { active = false; };
  }, [router]);
  const firstName = me?.name?.trim().split(/\s+/)[0] || "Cliente";
  const initial = firstName.charAt(0).toLocaleUpperCase("pt-BR");
  return <main className="mx-auto min-h-screen max-w-md bg-gradient-to-b from-slate-50 via-white to-white px-5 pb-28 pt-6 text-slate-950">
    <header>
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Sua área</p>
      <h1 className="mt-1 text-[28px] font-black tracking-tight">Minha conta</h1>
      <p className="mt-1 text-sm text-slate-500">Tudo sobre seus pedidos em um só lugar.</p>
    </header>
    {me && <section className="mt-6 rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.45)]" aria-label="Perfil do cliente">
      <div className="flex items-center gap-3.5">
        <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-slate-950 text-lg font-black text-white shadow-lg shadow-slate-950/15" aria-hidden="true">{initial}</div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-base font-extrabold">Olá, {firstName}</p>
          <div className="mt-1 flex items-center gap-1.5 text-xs font-medium text-emerald-700"><ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />Conta verificada</div>
        </div>
      </div>
      <div className="mt-4 grid gap-2 rounded-2xl bg-slate-50 px-3.5 py-3 text-xs text-slate-600">
        <p className="flex items-center gap-2"><span className="grid h-6 w-6 place-items-center rounded-lg bg-white text-slate-500 shadow-sm">{me.verification_method === "email" ? <Mail className="h-3.5 w-3.5" aria-hidden="true" /> : <Phone className="h-3.5 w-3.5" aria-hidden="true" />}</span><span className="truncate">{me.verification_method === "email" ? `E-mail verificado: ${me.email_masked}` : `Telefone verificado: ${me.phone_masked}`}</span></p>
        {me.verification_method === "email" && <p className="flex items-center gap-2"><span className="grid h-6 w-6 place-items-center rounded-lg bg-white text-slate-500 shadow-sm"><Phone className="h-3.5 w-3.5" aria-hidden="true" /></span><span>Celular para contato: {me.phone_masked}</span></p>}
      </div>
    </section>}
    {me?.loyalty?.enabled && <section className="relative mt-4 overflow-hidden rounded-[24px] bg-slate-950 p-5 text-white shadow-[0_20px_45px_-24px_rgba(15,23,42,0.75)]" aria-label="Programa de pontos">
      <div className="absolute -right-8 -top-10 h-36 w-36 rounded-full bg-amber-300/15 blur-2xl" aria-hidden="true" />
      <div className="absolute -bottom-14 -left-10 h-32 w-32 rounded-full bg-rose-400/10 blur-2xl" aria-hidden="true" />
      <div className="relative">
        <div className="flex items-center justify-between">
          <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-white/65"><Sparkles className="h-4 w-4 text-amber-300" aria-hidden="true" />Clube de pontos</p>
          <span className="grid h-9 w-9 place-items-center rounded-xl border border-white/10 bg-white/10"><Gift className="h-4 w-4 text-amber-200" aria-hidden="true" /></span>
        </div>
        <div className="mt-5 flex items-end justify-between gap-4">
          <div><p className="text-4xl font-black tracking-tight">{me.loyalty.available_points.toLocaleString("pt-BR")}</p><p className="mt-1 text-xs text-white/60">pontos disponíveis</p></div>
          <span className="rounded-full border border-amber-200/20 bg-amber-200/10 px-3 py-1.5 text-[11px] font-semibold text-amber-100">Seu saldo</span>
        </div>
        <div className="mt-5 flex items-center gap-2 border-t border-white/10 pt-4 text-xs text-white/55">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-300" aria-hidden="true" />
          {me.loyalty.lifetime_points > 0
            ? `${me.loyalty.lifetime_points.toLocaleString("pt-BR")} pontos acumulados desde o início`
            : "Faça pedidos nesta loja para começar a acumular pontos."}
        </div>
      </div>
    </section>}
    {error && <p role="alert" className="mt-4 rounded-2xl bg-red-50 p-3 text-sm font-medium text-red-700">{error}</p>}
    <section className="mt-7" aria-label="Opções da conta">
      <h2 className="mb-3 text-xs font-bold uppercase tracking-[0.16em] text-slate-400">Sua conta</h2>
      <div className="overflow-hidden rounded-[22px] border border-slate-200/80 bg-white shadow-[0_12px_35px_-28px_rgba(15,23,42,0.5)]">
        <Link className="group flex min-h-16 items-center gap-3.5 border-b border-slate-100 px-4 py-3.5 transition hover:bg-slate-50" href={accountHref("/account/orders")}>
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-rose-50 text-rose-600"><ReceiptText className="h-[18px] w-[18px]" aria-hidden="true" /></span>
          <span className="min-w-0 flex-1"><b className="block text-sm">Meus pedidos</b><span className="mt-0.5 block text-xs text-slate-500">Acompanhe e consulte seu histórico</span></span>
          <ChevronRight className="h-4 w-4 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-slate-500" aria-hidden="true" />
        </Link>
        <Link className="group flex min-h-16 items-center gap-3.5 px-4 py-3.5 transition hover:bg-slate-50" href={accountHref("/account/addresses")}>
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-sky-50 text-sky-600"><MapPin className="h-[18px] w-[18px]" aria-hidden="true" /></span>
          <span className="min-w-0 flex-1"><b className="block text-sm">Meus endereços</b><span className="mt-0.5 block text-xs text-slate-500">Gerencie seus locais de entrega</span></span>
          <ChevronRight className="h-4 w-4 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-slate-500" aria-hidden="true" />
        </Link>
      </div>
      <button disabled={busy} className="mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl text-sm font-semibold text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 disabled:opacity-50" onClick={async () => {
        setBusy(true); setError("");
        try { await logoutCustomer(); router.replace(customerAccountUrl("/account/login")); }
        catch { setError("Não foi possível encerrar a sessão. Tente novamente."); }
        finally { setBusy(false); }
      }}><LogOut className="h-4 w-4" aria-hidden="true" />{busy ? "Saindo..." : "Sair"}</button>
    </section>
  </main>;
}
