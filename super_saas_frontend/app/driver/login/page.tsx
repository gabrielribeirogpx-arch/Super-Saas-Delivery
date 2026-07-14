"use client";

import Image from "next/image";
import { FormEvent, Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { driverLogin } from "@/services/driverApi";
import { saveDriverSession } from "@/lib/driverAuth";

function DriverLoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const data = await driverLogin(email, password);
      if (!data?.token || !["driver", "delivery"].includes(String(data.driver?.role || "").toLowerCase())) {
        setError("Usuário não autorizado para a área do entregador.");
        return;
      }
      saveDriverSession(data.token);
      router.replace(searchParams.get("next") || "/driver/dashboard");
    } catch (err: any) {
      if (err?.status === 401 || err?.status === 403) {
        setError("Credenciais inválidas para este restaurante.");
      } else if (err?.status === 400 || err?.status === 404) {
        setError("Restaurante não encontrado para este endereço.");
      } else {
        setError("Erro de conexão. Verifique sua internet e tente novamente.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 px-4 py-8">
      <section className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-2xl">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <Image src="/service-delivery-logo.svg" alt="Service Delivery" width={72} height={72} priority />
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-600">Service Delivery</p>
            <h1 className="mt-1 text-2xl font-extrabold text-slate-900">Área do entregador</h1>
          </div>
        </div>

        <form className="space-y-4" onSubmit={submit}>
          <label className="block text-sm font-semibold text-slate-700">
            E-mail
            <input
              className="mt-1 w-full rounded-2xl border border-slate-200 px-4 py-3 text-base outline-none ring-emerald-500 transition focus:ring-2"
              autoComplete="email"
              inputMode="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label className="block text-sm font-semibold text-slate-700">
            Senha
            <input
              className="mt-1 w-full rounded-2xl border border-slate-200 px-4 py-3 text-base outline-none ring-emerald-500 transition focus:ring-2"
              autoComplete="current-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>

          {error && <p className="rounded-2xl bg-red-50 p-3 text-sm font-medium text-red-700">{error}</p>}

          <button
            className="w-full rounded-2xl bg-emerald-600 px-4 py-3 text-base font-bold text-white shadow-lg shadow-emerald-600/20 transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-70"
            disabled={loading}
            type="submit"
          >
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </section>
    </main>
  );
}

export default function DriverLoginPage() {
  return (
    <Suspense fallback={<main className="flex min-h-screen items-center justify-center bg-slate-950 px-4 py-8 text-white">Carregando...</main>}>
      <DriverLoginForm />
    </Suspense>
  );
}
