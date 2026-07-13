"use client";

import Image from "next/image";
import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import serviceDeliveryLogo from "../../public/service-delivery-logo.svg";
import { authApi } from "@/lib/auth";

const schema = z.object({
  email: z.string().email("Email inválido"),
  password: z.string().min(1, "Senha obrigatória"),
});

type FormValues = z.infer<typeof schema>;

function LoginInner() {
  const [error, setError] = useState<string | null>(null);
  const searchParams = useSearchParams();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = async (data: FormValues) => {
    setError(null);
    try {
      await authApi.login({
        email: data.email,
        password: data.password,
      });
      await authApi.me();

      const redirectParam = searchParams?.get("redirect");
      const safeRedirect = redirectParam?.startsWith("/")
        ? redirectParam
        : "/dashboard";

      window.location.replace(safeRedirect);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro ao autenticar";
      setError(message);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 via-white to-slate-100 px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="items-center space-y-3 pb-5 text-center">
          <Image
            src={serviceDeliveryLogo}
            alt="Service Delivery"
            width={190}
            height={66}
            className="h-auto w-[145px] sm:w-[170px] md:w-[190px]"
            priority
          />
          <div className="space-y-1.5">
            <CardTitle>Bem-vindo ao Service Delivery</CardTitle>
            <p className="text-sm text-slate-600">Faça login para acessar sua loja.</p>
          </div>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Email</label>
              <Input type="email" placeholder="admin@empresa.com" {...register("email")} />
              {errors.email && (
                <p className="text-xs text-red-600">{errors.email.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Senha</label>
              <Input type="password" placeholder="••••••••" {...register("password")} />
              {errors.password && (
                <p className="text-xs text-red-600">{errors.password.message}</p>
              )}
            </div>
            {error && (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {error}
              </div>
            )}
            <Button className="w-full" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Entrando..." : "Entrar"}
            </Button>
            <p className="text-center text-sm text-slate-600">
              Ainda não tem loja? <Link className="text-blue-700 underline" href="/onboarding">Criar loja</Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginInner />
    </Suspense>
  );
}
