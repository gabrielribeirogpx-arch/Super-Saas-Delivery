import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Fomizero | Gestão do restaurante",
  description: "Pedidos, cozinha e gestão do seu restaurante em um só lugar.",
  applicationName: "Fomizero",
  manifest: "/admin-manifest.webmanifest",
  appleWebApp: { capable: true, title: "Fomizero", statusBarStyle: "default" },
  icons: { icon: "/brand/fomizero-avatar-app.svg", apple: "/icons/fomizero-180.png" },
};

export const dynamic = "force-dynamic";

import { PlanAccessBoundary } from "@/components/plan-access-boundary";
import { AuthGuard } from "@/components/auth-guard";
import { AdminPageTransition } from "@/components/admin-page-transition";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";
import { AdminPwaProvider } from "@/components/pwa/AdminPwaProvider";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminPwaProvider>
      <AuthGuard>
        <div className="admin-shell flex min-h-screen lg:h-screen lg:min-h-0 lg:overflow-hidden">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col lg:min-h-0">
            <Topbar />
            <main className="flex-1 admin-content space-y-6 px-4 pt-5 md:px-6 lg:pb-6 lg:pt-4 lg:min-h-0 lg:overflow-y-auto">
              <PlanAccessBoundary><AdminPageTransition>{children}</AdminPageTransition></PlanAccessBoundary>
            </main>
          </div>
        </div>
      </AuthGuard>
    </AdminPwaProvider>
  );
}
