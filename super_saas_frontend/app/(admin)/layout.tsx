export const dynamic = "force-dynamic";

import { AuthGuard } from "@/components/auth-guard";
import { AdminPageTransition } from "@/components/admin-page-transition";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="admin-shell flex min-h-screen">
        <Sidebar />
        <div className="flex flex-1 flex-col">
          <Topbar />
          <main className="flex-1 space-y-6 p-4 md:p-6">
            <AdminPageTransition>{children}</AdminPageTransition>
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
