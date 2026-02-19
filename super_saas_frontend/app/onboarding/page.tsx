"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { onboardingApi } from "@/lib/onboarding";

type OnboardingForm = {
  businessName: string;
  adminName: string;
  adminEmail: string;
  adminPassword: string;
};

function generateSlug(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
}

export default function OnboardingPage() {
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<1 | 2>(1);

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
      const payload = {
        business_name: values.businessName,
        slug: generateSlug(values.businessName),
        admin_name: values.adminName,
        admin_email: values.adminEmail,
        admin_password: values.adminPassword,
      };

      const created = await onboardingApi.createTenant(payload);

      const tenantSlug = created.tenant_slug || created.slug;
      const adminUrl = `/t/${tenantSlug}/login`;
      sessionStorage.setItem(
        "onboarding:auto-login",
        JSON.stringify({
          tenantSlug,
          email: values.adminEmail,
          password: values.adminPassword,
        }),
      );
      window.location.assign(adminUrl);
    } catch (err) {
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
        <CardHeader>
          <CardTitle>Criação da sua loja</CardTitle>
          <p className="text-sm text-slate-600">Etapa {step} de 2</p>
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

                <div className="flex gap-2">
                  <Button type="button" variant="outline" onClick={() => setStep(1)}>
                    Voltar
                  </Button>
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? "Criando loja..." : "Criar loja"}
                  </Button>
                </div>
              </>
            )}

            {error && <div className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div>}

            <p className="text-center text-sm text-slate-600">
              Já possui conta? <Link className="text-blue-700 underline" href="/login">Entrar</Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
