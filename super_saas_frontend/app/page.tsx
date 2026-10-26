import type { Metadata } from "next";
import { redirect } from "next/navigation";

import SalesPage from "@/components/sales/SalesPage";

export const metadata: Metadata = process.env.NEXT_PUBLIC_SALES_SITE_ENABLED === "true" ? { title: "Fomizero | Gestão para seu delivery", description: "Planos mensais para organizar cardápio, pedidos, cozinha, entregas e financeiro.", manifest: null, applicationName: "Fomizero", appleWebApp: null } : {};

export default function HomePage() {
  if (process.env.NEXT_PUBLIC_SALES_SITE_ENABLED === "true") return <SalesPage />;
  redirect("/storefront");
}
