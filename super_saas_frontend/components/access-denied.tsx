"use client";

import Link from "next/link";
import { LockKeyhole } from "lucide-react";

import { Button } from "@/components/ui/button";

interface AccessDeniedProps {
  backHref: string;
}

export function AccessDenied({ backHref }: AccessDeniedProps) {
  return (
    <section className="mx-auto flex min-h-[55vh] max-w-xl items-center justify-center" role="alert">
      <div className="w-full rounded-xl border border-amber-200 bg-amber-50 p-8 text-center shadow-sm">
        <LockKeyhole className="mx-auto mb-4 h-10 w-10 text-amber-700" aria-hidden="true" />
        <h1 className="text-xl font-semibold text-slate-900">Acesso restrito</h1>
        <p className="mt-2 text-sm text-slate-700">
          Você não tem permissão para acessar esta área.
        </p>
        <p className="mt-1 text-sm text-slate-600">
          Entre em contato com o administrador da conta caso precise desse acesso.
        </p>
        <Button asChild className="mt-6">
          <Link href={backHref}>Voltar para uma área permitida</Link>
        </Button>
      </div>
    </section>
  );
}
