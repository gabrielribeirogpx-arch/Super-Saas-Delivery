import Link from "next/link";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";

export type RequestErrorKind = "unauthenticated" | "forbidden" | "server" | "network" | "other";

export function classifyRequestError(error: unknown): RequestErrorKind {
  if (error instanceof ApiError) {
    if (error.status === 401) return "unauthenticated";
    if (error.status === 403) return "forbidden";
    if (error.status >= 500) return "server";
    return "other";
  }
  return error instanceof TypeError ? "network" : "other";
}

export function RequestErrorState({ error }: { error: unknown }) {
  const kind = classifyRequestError(error);

  if (kind === "unauthenticated") {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800" role="alert">
        Sua sessão expirou. <Link className="font-semibold underline" href="/login">Entrar novamente</Link>
      </div>
    );
  }

  const message = kind === "network"
    ? "Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente."
    : kind === "server"
      ? "O servidor encontrou um erro ao processar a solicitação. Tente novamente mais tarde."
      : "Não foi possível concluir a solicitação.";

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700" role="alert">
      {message}
    </div>
  );
}
