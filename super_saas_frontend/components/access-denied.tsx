"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowLeft, LockKeyhole } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useSession } from "@/hooks/use-session";
import { permittedLandingPath } from "@/lib/authorization";

interface AccessDeniedProps {
  backHref?: string;
}

export function AccessDenied({ backHref }: AccessDeniedProps) {
  const { data: session } = useSession();
  const pathname = usePathname();
  const landing = session ? permittedLandingPath(session) : "/dashboard";
  const destination = backHref ?? (pathname === landing ? "/profile" : landing);

  return (
    <section className="mx-auto flex min-h-[60vh] w-full max-w-xl items-center px-3 py-8 sm:px-0" role="alert" aria-labelledby="access-denied-title">
      <div className="w-full overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm sm:p-10">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
          <LockKeyhole className="h-8 w-8" aria-hidden="true" />
        </div>
        <p className="mt-6 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Permissão da conta</p>
        <h1 id="access-denied-title" className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">Acesso restrito</h1>
        <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-slate-600">
          Seu perfil não tem permissão para visualizar esta área. Se você precisa desse acesso, peça ao administrador da loja para revisar suas permissões.
        </p>
        <Button asChild className="mt-7 w-full gap-2 sm:w-auto">
          <Link href={destination}><ArrowLeft className="h-4 w-4" aria-hidden="true" /> Voltar ao início</Link>
        </Button>
      </div>
    </section>
  );
}
