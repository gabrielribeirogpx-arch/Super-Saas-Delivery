"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiFetch } from "@/lib/api";

const schema = z.object({
  email: z.string().email("Email inválido"),
  password: z.string().min(1, "Senha obrigatória"),
});

type FormValues = z.infer<typeof schema>;

export default function TenantLoginPage() {
  const { slug } = useParams<{ slug: string }>();
  const hostSubdomain = typeof window !== "undefined" ? window.location.hostname.split(".")[0] : undefined;
  const effectiveSlug = hostSubdomain;
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = async (data: FormValues) => {
    if (!effectiveSlug || (slug && slug !== effectiveSlug)) {
      setError("Tenant inválido");
      return;
    }

    setError(null);
    try {
      const response = await apiFetch("/api/admin/auth/login", {
        method: "POST",
        headers: {
          "x-tenant-slug": effectiveSlug,
        },
        body: {
          email: data.email,
          password: data.password,
        },
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        const detail = typeof data?.detail === "string" ? data.detail : "Erro ao autenticar";
        throw new Error(detail);
      }

      const payload = (await response.json()) as { redirect_url?: string };
      const redirect = searchParams.get("redirect");
      router.push(redirect || payload.redirect_url || "/dashboard");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro ao autenticar";
      setError(message);
    }
  };

  useEffect(() => {
    const raw = sessionStorage.getItem("onboarding:auto-login");
    if (!raw) return;
    try {
      const saved = JSON.parse(raw) as { tenantSlug?: string; email?: string; password?: string };
      if (saved.tenantSlug === effectiveSlug && saved.email && saved.password) {
        setValue("email", saved.email);
        setValue("password", saved.password);
        void onSubmit({ email: saved.email, password: saved.password });
      }
    } finally {
      sessionStorage.removeItem("onboarding:auto-login");
    }
  }, [effectiveSlug, setValue]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 via-white to-slate-100 px-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Acesso administrativo</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Email</label>
              <Input type="email" placeholder="admin@empresa.com" {...register("email")} />
              {errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Senha</label>
              <Input type="password" placeholder="••••••••" {...register("password")} />
              {errors.password && <p className="text-xs text-red-600">{errors.password.message}</p>}
            </div>
            {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
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
