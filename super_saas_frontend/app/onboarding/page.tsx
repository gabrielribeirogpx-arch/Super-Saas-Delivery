"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import logo from "../../public/fomizero-logo.svg";
import { onboardingApi, type OnboardingResponse } from "@/lib/onboarding";
import { buildTenantPublicUrl } from "@/lib/platformDomains";
import Turnstile from "@/components/sales/Turnstile";
import { api } from "@/lib/api";
import { selectedPlan, type SalesConfig } from "@/lib/sales";
import { trackSalesEvent } from "@/lib/metaPixel";
import { trackSalesAnalyticsEvent } from "@/lib/salesAnalytics";
import { validatedHotmartCheckout } from "@/lib/subscriptions";
import { rememberStore } from "@/lib/recentStore";

type Form = { businessName: string; adminName: string; adminEmail: string; adminPassword: string };
const money = (cents: number) => (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export default function OnboardingPage() {
  const submitting = useRef(false);
  const [changingPlan, setChangingPlan] = useState(false);
  const [config, setConfig] = useState<SalesConfig | null>(null);
  const [captcha, setCaptcha] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [accepted, setAccepted] = useState(false);
  const [plan, setPlan] = useState<string | null>(null);
  const [invitation, setInvitation] = useState<string | undefined>();
  const [error, setError] = useState("");
  const [created, setCreated] = useState<OnboardingResponse | null>(null);
  const [returned, setReturned] = useState(false);
  const [checkoutUrl, setCheckoutUrl] = useState("");
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<Form>();
  useEffect(() => {
    setPlan(selectedPlan(new URLSearchParams(window.location.search).get("plan")));
    api.get<SalesConfig>("/api/onboarding/sales-config").then(setConfig).catch(() => {});
    try { sessionStorage.removeItem("onboarding:auto-login"); } catch { /* Storage is optional. */ }
    const incoming = new URLSearchParams(window.location.hash.slice(1)).get("invite");
    if (incoming !== null) {
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
      if (/^[A-Za-z0-9_-]{43}$/.test(incoming)) {
        try { sessionStorage.setItem("onboarding:invite", incoming); } catch { /* Keep invitation in memory. */ }
        setInvitation(incoming);
      } else {
        try { sessionStorage.removeItem("onboarding:invite"); } catch { /* Storage is optional. */ }
        setError("Convite inválido. Solicite um novo convite ao Fomizero.");
      }
    } else {
      try { setInvitation(sessionStorage.getItem("onboarding:invite") ?? undefined); } catch { /* Public enrollment still works. */ }
    }
    const onReturn = (event: PageTransitionEvent) => { if (event.persisted) setReturned(true); };
    window.addEventListener("pageshow", onReturn);
    return () => window.removeEventListener("pageshow", onReturn);
  }, []);
  const offer = config?.offers.find(o => o.code === plan);
  const loginUrl = created ? buildTenantPublicUrl(created.slug, "/login?redirect=" + encodeURIComponent("/subscriptions")) : "";
  function openCheckout(url: string) {
    try { window.location.assign(validatedHotmartCheckout(url)); }
    catch { setError("Sua loja já foi criada. Use o botão abaixo para continuar ou consulte sua assinatura."); }
  }
  async function submit(values: Form) {
    if (submitting.current) return;
    submitting.current = true;
    setError("");
    let result: OnboardingResponse;
    try {
      result = await onboardingApi.createTenant({ business_name: values.businessName, admin_name: values.adminName,
        admin_email: values.adminEmail, admin_password: values.adminPassword,
        ...(offer ? { plan_code: offer.code } : {}),
        ...(!invitation ? { captcha_token: captcha, accept_terms: accepted, terms_version: config?.terms_version } : {}),
      }, invitation);
    } catch (err) {
      submitting.current = false;
      setCaptcha(""); setAttempt(n => n + 1);
      setError(err instanceof Error ? err.message : "Não foi possível criar sua loja. Tente novamente.");
      return;
    }
    setCreated(result); reset(); rememberStore(result.slug);
    try { sessionStorage.removeItem("onboarding:invite"); } catch { /* Storage is optional. */ }
    if (offer && result.checkout_url) {
      trackSalesEvent("CompleteRegistration");
      trackSalesAnalyticsEvent("sign_up", offer);
    }
    setReturned(false);
    if (result.checkout_url) {
      try {
        const url = validatedHotmartCheckout(result.checkout_url);
        setCheckoutUrl(url);
        if (offer) {
          trackSalesEvent("InitiateCheckout", offer);
          trackSalesAnalyticsEvent("begin_checkout", offer);
        }
        openCheckout(url);
      } catch { setError("Sua loja foi criada, mas não foi possível abrir o pagamento. Entre na loja para continuar sua contratação."); }
    } else {
      // Backward-compatible invitations/operator enrollment without a selected offer.
      window.location.assign(buildTenantPublicUrl(result.slug, result.subscription_required ? "/login?redirect=/subscriptions" : "/login"));
    }
  }
  return <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-8">
    <Card className="w-full max-w-xl">
      <CardHeader className="items-center space-y-3 text-center"><Image src={logo} alt="Fomizero" width={190} height={53} className="h-auto max-w-full object-contain" priority />
        <CardTitle>{created ? "Sua loja foi criada" : "Vamos preparar sua loja"}</CardTitle>
        <p className="text-sm text-slate-600">{created ? "Guarde o endereço abaixo para acessar seu restaurante." : "Crie seu acesso e continue para o pagamento seguro na Hotmart."}</p>
        {invitation && !created && <p className="text-sm text-emerald-700">Cadastro por convite.</p>}
      </CardHeader>
      <CardContent>
        {created ? <section className="space-y-4" aria-label="Loja criada">
          <p className="break-all rounded-lg border bg-slate-50 p-3 text-sm">{buildTenantPublicUrl(created.slug)}</p>
          <p className="text-sm">Use o e-mail <strong>{created.admin_email}</strong> e a senha que você cadastrou para entrar depois.</p>
          {checkoutUrl && !returned && <Button className="w-full" onClick={() => openCheckout(checkoutUrl)}>Continuar para o pagamento na Hotmart</Button>}
          <a className="block rounded border p-3 text-center text-sm" href={loginUrl}>Entrar na loja e consultar assinatura</a>
          <p className="text-sm text-slate-600">Se já pagou, consulte sua assinatura antes de tentar pagar novamente. A liberação depende da confirmação da Hotmart e pode levar alguns minutos.</p>
        </section> : <form className="grid gap-4" onSubmit={handleSubmit(submit)}>
          {offer && <div className="rounded-lg border bg-slate-50 p-4 text-sm"><strong>{offer.name} — {money(offer.price_cents)} / mês</strong><p className="mt-1">Você conferirá as condições antes de pagar na Hotmart.</p><button type="button" className="mt-2 underline" aria-expanded={changingPlan} onClick={() => setChangingPlan(v => !v)}>Trocar plano</button></div>}
          {config?.offers.length && (!offer || changingPlan) ? <label className="grid gap-1 text-sm">Plano escolhido<select aria-label="Plano escolhido" className="rounded border bg-white p-2" value={plan ?? ""} onChange={e => setPlan(e.target.value || null)}><option value="">Escolha seu plano</option>{config.offers.map(o => <option key={o.code} value={o.code}>{o.name} — {money(o.price_cents)} / mês</option>)}</select></label> : null}
          <label className="grid gap-1 text-sm">Nome do restaurante<Input autoComplete="organization" placeholder="Nome do restaurante" {...register("businessName", { required: "Informe o nome do restaurante", pattern: { value: /\S/, message: "Informe o nome do restaurante" }, minLength: { value: 2, message: "Use ao menos 2 caracteres" }, maxLength: 120 })} /></label>
          {errors.businessName && <p className="text-xs text-red-600">{errors.businessName.message}</p>}
          <label className="grid gap-1 text-sm">Seu nome<Input autoComplete="name" placeholder="Nome do administrador" {...register("adminName", { required: "Informe seu nome", pattern: { value: /\S/, message: "Informe seu nome" }, minLength: { value: 2, message: "Use ao menos 2 caracteres" }, maxLength: 120 })} /></label>
          {errors.adminName && <p className="text-xs text-red-600">{errors.adminName.message}</p>}
          <label className="grid gap-1 text-sm">E-mail de acesso<Input type="email" autoComplete="email" placeholder="admin@restaurante.com" {...register("adminEmail", { required: "Informe seu e-mail" })} /></label>
          {errors.adminEmail && <p className="text-xs text-red-600">{errors.adminEmail.message}</p>}
          <label className="grid gap-1 text-sm">Crie sua senha<Input type="password" autoComplete="new-password" placeholder="Mínimo 8 caracteres" {...register("adminPassword", { required: "Crie uma senha", minLength: { value: 8, message: "Use ao menos 8 caracteres" }, maxLength: 200 })} /></label>
          {errors.adminPassword && <p className="text-xs text-red-600">{errors.adminPassword.message}</p>}
          {!invitation && config?.ready && <>
            <label className="flex gap-2 text-sm"><input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} /><span>Li e aceito os <a className="underline" href={config.terms_url} target="_blank" rel="noopener noreferrer">termos de uso</a> e li a <a className="underline" href={config.privacy_url} target="_blank" rel="noopener noreferrer">política de privacidade</a>.</span></label>
            <Turnstile siteKey={config.site_key} onToken={setCaptcha} attempt={attempt} />
          </>}
          {!invitation && !config?.ready && <p role="status" className="text-sm">O cadastro público está indisponível. Se recebeu um convite, abra o link completo.</p>}
          <Button type="submit" disabled={isSubmitting || (!invitation && (!config?.ready || !offer || !accepted || !captcha))}>{isSubmitting ? "Preparando sua loja..." : offer ? "Criar loja e ir para o pagamento" : "Criar loja"}</Button>
          <p className="text-center text-sm text-slate-600">O cadastro não gera cobrança. Cardápio, horários e entregas você configura depois.</p>
          <p className="text-center text-sm">Já criou sua loja? <Link className="underline" href="/continuar">Entrar ou retomar contratação</Link></p>
        </form>}
        {error && <p role="alert" className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      </CardContent>
    </Card>
  </main>;
}
