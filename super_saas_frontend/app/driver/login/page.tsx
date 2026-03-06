"use client";

import { FormEvent, useEffect, useState } from "react";
import { ApiError, api } from "@/services/api";

function resolveTenantFromHostname(hostname: string): string | null {
  const normalizedHost = hostname.trim().toLowerCase().split(":")[0];
  if (!normalizedHost) {
    return null;
  }

  const baseDomain = "servicedelivery.com.br";
  if (normalizedHost === baseDomain || !normalizedHost.endsWith(`.${baseDomain}`)) {
    return null;
  }

  const prefix = normalizedHost.slice(0, -(baseDomain.length + 1));
  if (!prefix) {
    return null;
  }

  const labels = prefix.split(".").filter(Boolean);
  const tenant = labels[labels.length - 1];
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
      const { data } = await api.post<{ access_token?: string; token?: string }>(
        "/api/delivery/auth/login",
        {
          email: email.trim().toLowerCase(),
          password,
        },
        {
          headers: {
            "X-Tenant-ID": tenant,
          },
        }
      );

      const token = data.access_token || data.token;

      if (!token) {
        throw new Error("Login failed");
      }

      localStorage.setItem("driver_token", token);
      window.location.href = "/driver/dashboard";
    } catch (loginError) {
      console.error("Driver login error:", loginError);
      if (loginError instanceof ApiError && loginError.response?.data && typeof loginError.response.data === "object") {
        const detail = (loginError.response.data as { detail?: string }).detail;
        setError(detail || "Verifique e-mail e senha");
      } else {
        setError(loginError instanceof Error ? loginError.message : "Verifique e-mail e senha");
      }
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
