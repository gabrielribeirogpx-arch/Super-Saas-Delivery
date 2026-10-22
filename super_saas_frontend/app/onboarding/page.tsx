"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import fomizeroLogo from "../../public/fomizero-logo.svg";
import { onboardingApi } from "@/lib/onboarding";
import { buildTenantPublicUrl } from "@/lib/platformDomains";

import Turnstile from "@/components/sales/Turnstile";
import { api } from "@/lib/api";
import { selectedPlan, type SalesConfig } from "@/lib/sales";
import { trackSalesEvent } from "@/lib/metaPixel";

type OnboardingForm = {
  businessName: string;
  adminName: string;
  adminEmail: string;
  adminPassword: string;
};

export default function OnboardingPage() {
  const [config, setConfig] = useState<SalesConfig | null>(null);
  const [captcha, setCaptcha] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [accepted, setAccepted] = useState(false);
  const [plan, setPlan] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<1 | 2>(1);
  const [invitation, setInvitation] = useState<string | undefined>();
  useEffect(() => {
    setPlan(selectedPlan(new URLSearchParams(window.location.search).get("plan")));
    api.get<SalesConfig>("/api/onboarding/sales-config").then(setConfig).catch(() => {});
    sessionStorage.removeItem("onboarding:auto-login");
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    const incoming = fragment.get("invite");
    if (incoming !== null) {
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
      if (/^[A-Za-z0-9_-]{43}$/.test(incoming)) {
        sessionStorage.setItem("onboarding:invite", incoming);
        setInvitation(incoming);
      } else {
        sessionStorage.removeItem("onboarding:invite");
        setError("Convite inválido. Solicite um novo convite ao Fomizero.");
      }
    } else {
      setInvitation(sessionStorage.getItem("onboarding:invite") ?? undefined);
    }
  }, []);

  const {
    register,
    handleSubmit,
    trigger,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<OnboardingForm>();

  const goToStepTwo = async () => {
    const valid = await trigger("businessName");
    if (valid) {
      setStep(2);
    }
  };

  const onSubmit = async (values: OnboardingForm) => {
    setError(null);
    try {
      const { businessName, adminName, adminEmail, adminPassword } = values;

      const payload = {
        business_name: businessName,
        admin_name: adminName,
        admin_email: adminEmail,
        admin_password: adminPassword,
        ...(!invitation ? { captcha_token: captcha, accept_terms: accepted, terms_version: config?.terms_version } : {}),
      };

      const created = await onboardingApi.createTenant(payload, invitation);
      sessionStorage.removeItem("onboarding:invite");

      trackSalesEvent("CompleteRegistration");
      const tenantSlug = created.slug;
      const next = "/subscriptions" + (plan ? `?plan=${encodeURIComponent(plan)}` : "");
      const adminUrl = buildTenantPublicUrl(tenantSlug, created.subscription_required ? `/login?redirect=${encodeURIComponent(next)}` : "/login");
      sessionStorage.removeItem("onboarding:auto-login");
      window.location.href = adminUrl;
    } catch (err) {
      setCaptcha(""); setAttempt(n => n + 1);
      const axiosLikeError = err as {
        response?: { data?: { detail?: unknown } };
        data?: { detail?: unknown };
        message?: string;
      };

      const detail = axiosLikeError?.response?.data?.detail ?? axiosLikeError?.data?.detail;

      if (detail !== undefined && detail !== null) {
        setError(typeof detail === "string" ? detail : JSON.stringify(detail));
      } else if (axiosLikeError?.message) {
        setError(axiosLikeError.message);
      } else {
        setError("Erro inesperado ao criar loja.");
      }
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-8">
      <Card className="w-full max-w-xl">
        <CardHeader className="items-center space-y-3 pb-5 text-center">
          <Image
            src={fomizeroLogo}
            alt="Fomizero"
            width={190}
            height={50}
            className="h-auto w-[145px] object-contain sm:w-[170px] md:w-[190px]"
            priority
          />
          <div className="space-y-1.5">
            <CardTitle>Crie sua loja</CardTitle>
            <p className="text-sm text-slate-600">Configure sua loja em poucos minutos.</p>
            {invitation && <p className="text-sm text-emerald-700">Cadastro por convite. Após criar a loja, você poderá contratar sua assinatura.</p>}
            <p className="text-sm text-slate-600">Etapa {step} de 2</p>
          </div>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4" onSubmit={handleSubmit(onSubmit)}>
            {step === 1 ? (
              <>
                <Input placeholder="Nome do restaurante" {...register("businessName", { required: "Nome obrigatório" })} />
                {errors.businessName && <p className="text-xs text-red-600">{errors.businessName.message}</p>}

                <Button type="button" onClick={goToStepTwo}>
                  Continuar
                </Button>
              </>
            ) : (
              <>
                <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                  Restaurante: <strong>{getValues("businessName")}</strong>
                </div>

                <Input placeholder="Nome do administrador" {...register("adminName", { required: "Nome obrigatório" })} />
                {errors.adminName && <p className="text-xs text-red-600">{errors.adminName.message}</p>}

                <Input
                  type="email"
                  placeholder="admin@restaurante.com"
                  {...register("adminEmail", { required: "Email obrigatório" })}
                />
                {errors.adminEmail && <p className="text-xs text-red-600">{errors.adminEmail.message}</p>}

                <Input
                  type="password"
                  placeholder="Mínimo 8 caracteres"
                  {...register("adminPassword", {
                    required: "Senha obrigatória",
                    minLength: { value: 8, message: "Senha deve ter ao menos 8 caracteres" },
                  })}
                />
                {errors.adminPassword && <p className="text-xs text-red-600">{errors.adminPassword.message}</p>}

                {!invitation && config?.ready && <>
                  <label className="flex gap-2 text-sm"><input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} />
                    <span>Li e aceito os <a className="underline" href={config.terms_url} target="_blank" rel="noopener noreferrer">termos de uso</a> e li a <a className="underline" href={config.privacy_url} target="_blank" rel="noopener noreferrer">política de privacidade</a>.</span>
                  </label>
                  <Turnstile siteKey={config.site_key} onToken={setCaptcha} attempt={attempt} />
                </>}
                {!invitation && !config?.ready && <p role="status" className="text-sm">O cadastro público está indisponível. Se recebeu um convite, abra o link completo.</p>}
                <p className="text-sm text-slate-600">Guarde seu e-mail e senha. Após criar a loja, faça login para escolher e contratar seu plano. O cadastro não gera cobrança.</p>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" onClick={() => setStep(1)}>
                    Voltar
                  </Button>
                  <Button type="submit" disabled={isSubmitting || (!invitation && (!config?.ready || !accepted || !captcha))}>
                    {isSubmitting ? "Criando loja..." : "Criar loja"}
                  </Button>
                </div>
              </>
            )}

            {error && <div className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div>}

            <p className="text-center text-sm text-slate-600">
              Já possui conta? <Link className="text-brand-700 underline hover:text-brand-800" href="/entrar">Entrar</Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
