"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { authApi } from "@/lib/auth";
import { onboardingApi } from "@/lib/onboarding";

type OnboardingForm = {
  businessName: string;
  slug: string;
  customDomain: string;
  adminName: string;
  adminEmail: string;
  adminPassword: string;
};

export default function OnboardingPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [availability, setAvailability] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<OnboardingForm>();

  const handleCheck = async () => {
    const slug = getValues("slug");
    const customDomain = getValues("customDomain");
    if (!slug && !customDomain) {
      setAvailability("Informe slug ou domínio para checar disponibilidade.");
      return;
    }
    try {
      const response = await onboardingApi.checkAvailability(slug || undefined, customDomain || undefined);
      const bits: string[] = [];
      if (response.slug) {
        bits.push(`Slug '${response.slug}' ${response.slug_available ? "disponível" : "indisponível"}`);
      }
      if (response.custom_domain) {
        bits.push(`Domínio '${response.custom_domain}' ${response.custom_domain_available ? "disponível" : "indisponível"}`);
      }
      setAvailability(bits.join(" • "));
    } catch (err) {
      setAvailability(err instanceof Error ? err.message : "Falha ao checar disponibilidade");
    }
  };

  const onSubmit = async (values: OnboardingForm) => {
    setError(null);
    setAvailability(null);
    try {
      const created = await onboardingApi.createTenant({
        business_name: values.businessName,
        slug: values.slug || undefined,
        custom_domain: values.customDomain || undefined,
        admin_name: values.adminName,
        admin_email: values.adminEmail,
        admin_password: values.adminPassword,
      });

      await authApi.login({
        email: values.adminEmail,
        password: values.adminPassword,
      });
      router.push(`/t/${created.slug}/dashboard`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível concluir onboarding");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-8">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle>Criação da sua loja</CardTitle>
          <p className="text-sm text-slate-600">Configure tenant, admin proprietário e inicie em minutos.</p>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4" onSubmit={handleSubmit(onSubmit)}>
            <Input placeholder="Nome do restaurante" {...register("businessName", { required: "Nome obrigatório" })} />
            {errors.businessName && <p className="text-xs text-red-600">{errors.businessName.message}</p>}

            <div className="grid gap-2 md:grid-cols-2">
              <Input placeholder="slug-da-loja (opcional)" {...register("slug")} />
              <Input placeholder="dominio.com (opcional)" {...register("customDomain")} />
            </div>

            <Button type="button" variant="outline" onClick={handleCheck}>Checar disponibilidade</Button>
            {availability && <p className="text-xs text-slate-600">{availability}</p>}

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

            {error && <div className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div>}

            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Criando loja..." : "Criar loja"}
            </Button>

            <p className="text-center text-sm text-slate-600">
              Já possui conta? <Link className="text-blue-700 underline" href="/login">Entrar</Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
