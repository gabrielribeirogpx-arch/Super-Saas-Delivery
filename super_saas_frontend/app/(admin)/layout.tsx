export const dynamic = "force-dynamic";

import { AuthGuard } from "@/components/auth-guard";
import { AdminPageTransition } from "@/components/admin-page-transition";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="admin-shell flex min-h-screen lg:h-screen lg:min-h-0 lg:overflow-hidden">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col lg:min-h-0">
          <Topbar />
          <main className="flex-1 space-y-6 px-4 pb-4 pt-2 md:px-6 md:pb-6 md:pt-4 lg:min-h-0 lg:overflow-y-auto">
            <AdminPageTransition>{children}</AdminPageTransition>
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
