"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { customerAccountUrl } from "@/lib/customerAuth";
export default function MyOrdersPage() {
  const router = useRouter();
  useEffect(() => { router.replace(customerAccountUrl("/account/orders")); }, [router]);
  return <p className="p-6">Abrindo seus pedidos...</p>;
}
