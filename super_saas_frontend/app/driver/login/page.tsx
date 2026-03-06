"use client";

import { FormEvent, useEffect, useState } from "react";

function resolveTenantFromHostname(hostname: string): string | null {
  const tenant = hostname.trim().toLowerCase().split(".")[0];
  return tenant || null;
}

export default function DriverLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const tenant = resolveTenantFromHostname(window.location.hostname);

    if (tenant) {
      localStorage.setItem("tenant_id", tenant);
    }
  }, []);

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    const tenant = resolveTenantFromHostname(window.location.hostname) ?? localStorage.getItem("tenant_id");

    if (!tenant) {
      setError("Não foi possível identificar o tenant pelo domínio.");
      setLoading(false);
      return;
    }

    try {
      const response = await fetch("https://service-delivery-backend-production.up.railway.app/api/delivery/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-ID": tenant,
        },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Login failed");
      }

      localStorage.setItem("driver_token", data.access_token);
      window.location.href = "/driver/dashboard";
    } catch (loginError) {
      console.error("Driver login error:", loginError);
      setError(loginError instanceof Error ? loginError.message : "Verifique e-mail e senha");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center bg-slate-50 p-4">
      <h1 className="mb-4 text-2xl font-bold">Driver App</h1>
      <form onSubmit={handleLogin} className="space-y-3 rounded-lg border bg-white p-4">
        <label className="block text-sm font-medium">Email</label>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoCapitalize="none"
          autoCorrect="off"
          inputMode="email"
          className="w-full rounded border px-3 py-2"
          required
        />

        <label className="block text-sm font-medium">Senha</label>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="w-full rounded border px-3 py-2"
          required
        />

        {error ? <p className="text-sm text-rose-600">{error}</p> : null}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-60"
        >
          {loading ? "Entrando..." : "Entrar"}
        </button>
      </form>
    </main>
  );
}
