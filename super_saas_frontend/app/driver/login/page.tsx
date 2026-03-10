"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import DriverLayout from "@/components/driver/DriverLayout";
import { driverLogin } from "@/services/driverApi";

export default function DriverLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    try {
      const data = await driverLogin(email, password);
      localStorage.setItem("driver_token", data.token);
      router.push("/driver/dashboard");
    } catch (err: any) {
      setError(err?.message || "Login failed");
    }
  }

  return (
    <DriverLayout title="Driver Login">
      <div className="space-y-3">
        <input className="w-full rounded border p-3" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="w-full rounded border p-3" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button className="w-full rounded bg-blue-600 p-3 font-semibold text-white" onClick={submit}>LOGIN</button>
        {error && <p className="rounded bg-red-50 p-2 text-sm text-red-600">{error}</p>}
      </div>
    </DriverLayout>
  );
}
