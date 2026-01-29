import { AuthGuard } from "@/components/auth-guard";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

export default function TenantLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { tenantId: string };
}) {
  return (
    <AuthGuard>
      <div className="flex min-h-screen">
        <Sidebar tenantId={params.tenantId} />
        <div className="flex flex-1 flex-col">
          <Topbar tenantId={params.tenantId} />
          <main className="flex-1 space-y-6 p-6">{children}</main>
        </div>
      </div>
    </AuthGuard>
  );
}
